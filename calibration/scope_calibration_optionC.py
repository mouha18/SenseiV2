"""
Option C: can a richer doc-less anchor separate DESC cleanly across topics?

Baseline (description-only, RETRIEVAL_DOCUMENT) overlaps: global gap -0.007.
Here we test four anchor strategies and report the global in/out gap of each:

  1. baseline        — description only,            task RETRIEVAL_DOCUMENT, questions RETRIEVAL_QUERY
  2. centroid-doc    — mean(description + seeds),    task RETRIEVAL_DOCUMENT, questions RETRIEVAL_QUERY
  3. semsim-desc     — description only,             task SEMANTIC_SIMILARITY both sides
  4. semsim-centroid — mean(description + seeds),    task SEMANTIC_SIMILARITY both sides

Seeds are SEPARATE representative questions used only to build the anchor; the
original in_scope sets stay held-out for evaluation (no leakage).

Run:
    GEMINI_API_KEY=... calibration/.venv/Scripts/python.exe calibration/scope_calibration_optionC.py
"""

import time
import numpy as np
from google.genai import types
from scope_calibration_multi import TOPICS, GENERIC_OFF, client, MODEL, DIM

_req_times = []  # rolling-minute request timestamps (free tier ~100 embed items/min)


def embed(texts, task_type, max_per_min=80, batch=10):
    out = []
    for i in range(0, len(texts), batch):
        chunk = texts[i : i + batch]
        now = time.time()
        while _req_times and now - _req_times[0] > 60:
            _req_times.pop(0)
        if _req_times and len(_req_times) + len(chunk) > max_per_min:
            wait = 61 - (now - _req_times[0])
            if wait > 0:
                print(f"    ...rate-limit pause {wait:.0f}s")
                time.sleep(wait)
                _req_times.clear()
        for _ in range(6):  # 429 backoff
            try:
                resp = client.models.embed_content(
                    model=MODEL, contents=chunk,
                    config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=DIM),
                )
                break
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    print("    ...429, backing off 50s")
                    time.sleep(50)
                    _req_times.clear()
                else:
                    raise
        else:
            raise RuntimeError("repeated 429s — wait a minute and retry")
        out.extend(e.values for e in resp.embeddings)
        _req_times.extend([time.time()] * len(chunk))
    v = np.array(out, dtype=np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return v

# Anchor seed questions — representative, DISTINCT from the held-out in_scope sets.
SEEDS = {
    "Photosynthesis (biology)": [
        "How do plants make food from sunlight?", "What is the Calvin cycle?",
        "What role does chlorophyll play in plants?", "What are the products of photosynthesis?",
    ],
    "French Revolution (history)": [
        "What were the main causes of the French Revolution?", "What happened during the Reign of Terror?",
        "Who were the key figures of the French Revolution?", "How did the French monarchy fall?",
    ],
    "Derivatives (calculus)": [
        "What does a derivative measure?", "What are the basic rules of differentiation?",
        "How do you compute the derivative of a function?", "How are derivatives used to find extrema?",
    ],
    "HTTP and the web (CS)": [
        "How do browsers and servers communicate?", "What are HTTP methods?",
        "What do HTTP status codes mean?", "How does HTTPS protect data?",
    ],
}


def unit(v):
    return v / np.linalg.norm(v)


def evaluate(anchor, qemb, label):
    g_min_in, g_max_out, b_in, b_out = 1.0, 0.0, None, None
    for n in TOPICS:
        A = anchor[n]  # (k, d)

        def score(q):
            return float((A @ qemb[q]).max())

        ins = [(q, score(q)) for q in TOPICS[n]["in_scope"]]
        outs_qs = (TOPICS[n]["near_off"]
                   + [q for m in TOPICS if m != n for q in TOPICS[m]["in_scope"]]
                   + GENERIC_OFF)
        outs = [(q, score(q)) for q in outs_qs]
        mi_q, mi = min(ins, key=lambda x: x[1])
        mo_q, mo = max(outs, key=lambda x: x[1])
        if mi < g_min_in:
            g_min_in, b_in = mi, f"{n} | {mi_q}"
        if mo > g_max_out:
            g_max_out, b_out = mo, f"{n} | {mo_q}"
    gap = g_min_in - g_max_out
    verdict = "CLEAN — one threshold works" if gap > 0 else "OVERLAP"
    print(f"\n  [{label}]")
    print(f"    global min in-scope = {g_min_in:.3f}  [{b_in}]")
    print(f"    global max out      = {g_max_out:.3f}  [{b_out}]")
    print(f"    global gap          = {gap:+.3f}  -> {verdict}")
    if gap > 0:
        print(f"    midpoint = {(g_min_in + g_max_out)/2:.3f}   lean-wide pick ~ {g_max_out + 0.005:.3f}")
    return gap


def main():
    names = list(TOPICS.keys())
    descs = [TOPICS[n]["description"] for n in names]

    # Held-out evaluation questions.
    eval_qs = list({q for t in TOPICS.values() for q in t["in_scope"] + t["near_off"]} | set(GENERIC_OFF))

    # Embeddings in both task types.
    desc_doc = {n: v for n, v in zip(names, embed(descs, "RETRIEVAL_DOCUMENT"))}
    desc_ss = {n: v for n, v in zip(names, embed(descs, "SEMANTIC_SIMILARITY"))}
    q_query = {q: v for q, v in zip(eval_qs, embed(eval_qs, "RETRIEVAL_QUERY"))}
    q_ss = {q: v for q, v in zip(eval_qs, embed(eval_qs, "SEMANTIC_SIMILARITY"))}

    seed_flat = [s for n in names for s in SEEDS[n]]
    seed_doc_flat = embed(seed_flat, "RETRIEVAL_DOCUMENT")
    seed_ss_flat = embed(seed_flat, "SEMANTIC_SIMILARITY")
    # regroup seeds per topic
    seed_doc, seed_ss, i = {}, {}, 0
    for n in names:
        k = len(SEEDS[n])
        seed_doc[n] = seed_doc_flat[i : i + k]
        seed_ss[n] = seed_ss_flat[i : i + k]
        i += k

    # Strategy anchors (each topic -> (k,d) array; centroids are (1,d)).
    baseline = {n: desc_doc[n][None, :] for n in names}
    centroid_doc = {n: unit(np.vstack([desc_doc[n][None, :], seed_doc[n]]).mean(0))[None, :] for n in names}
    semsim_desc = {n: desc_ss[n][None, :] for n in names}
    semsim_centroid = {n: unit(np.vstack([desc_ss[n][None, :], seed_ss[n]]).mean(0))[None, :] for n in names}

    print("#" * 72)
    print("# Option C — DESC anchor strategies (goal: clean global gap)")
    print("#" * 72)
    evaluate(baseline, q_query, "1. baseline (desc only, retrieval)")
    evaluate(centroid_doc, q_query, "2. centroid-doc (desc + seeds, retrieval)")
    evaluate(semsim_desc, q_ss, "3. semsim-desc (desc only, semantic-similarity)")
    evaluate(semsim_centroid, q_ss, "4. semsim-centroid (desc + seeds, semantic-similarity)")


if __name__ == "__main__":
    main()
