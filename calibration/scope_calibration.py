"""
Throwaway calibration spike for Sensei's scope thresholds (ADR-0004).

NOT application code. Its only job: produce suggested values for
SCOPE_THRESHOLD_DESC (doc-less sessions) and SCOPE_THRESHOLD_DOC (doc sessions)
by embedding labeled in-/out-of-scope questions against a real anchor with
gemini-embedding-001 (1536-dim, MRL) and reporting where the two groups separate.

Run:
    pip install google-genai numpy
    # PowerShell:  $env:GEMINI_API_KEY="..."
    # bash:        export GEMINI_API_KEY=...
    python scope_calibration.py

The numbers it prints are a starting point, not gospel — eyeball the
distributions, then set the thresholds (and re-run after editing the samples
to match a real session's topic). See README.md.
"""

import os
import numpy as np
from google import genai
from google.genai import types

MODEL = "gemini-embedding-001"
DIM = 1536  # locked: MRL-truncated, fits pgvector's 2000-dim index cap

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def embed(texts, task_type):
    """Embed a list of strings; MRL output (<3072 dims) is re-normalized to unit length."""
    out = []
    for i in range(0, len(texts), 100):  # modest batches to stay clear of any per-call cap
        resp = client.models.embed_content(
            model=MODEL,
            contents=texts[i : i + 100],
            config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=DIM),
        )
        out.extend(e.values for e in resp.embeddings)
    vecs = np.array(out, dtype=np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)  # required for MRL dims != 3072
    return vecs


def sweep(in_scores, out_scores):
    """Find the threshold that best separates in- from out-of-scope; report separation."""
    in_arr, out_arr = np.array(in_scores), np.array(out_scores)
    candidates = np.linspace(0.0, 1.0, 1001)
    best_t, best_acc = 0.5, -1.0
    for t in candidates:
        acc = ((in_arr >= t).sum() + (out_arr < t).sum()) / (len(in_arr) + len(out_arr))
        if acc > best_acc:
            best_acc, best_t = acc, t
    return {
        "suggested_threshold": round(best_t, 3),
        "accuracy_at_threshold": round(best_acc, 3),
        "min_in_scope": round(float(in_arr.min()), 3),
        "max_out_of_scope": round(float(out_arr.max()), 3),
        "clean_gap": float(in_arr.min()) > float(out_arr.max()),
        "midpoint_if_separable": round((float(in_arr.min()) + float(out_arr.max())) / 2, 3),
    }


def report(title, anchor_vecs, questions_in, questions_out, anchor_is_chunkset):
    q_in = embed(questions_in, "RETRIEVAL_QUERY")
    q_out = embed(questions_out, "RETRIEVAL_QUERY")

    def score(qv):
        sims = anchor_vecs @ qv  # cosine (all unit-normalized)
        return float(sims.max()) if anchor_is_chunkset else float(sims[0])

    in_scores = [score(v) for v in q_in]
    out_scores = [score(v) for v in q_out]

    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")
    print("\n  IN-SCOPE (similarity to anchor):")
    for q, s in sorted(zip(questions_in, in_scores), key=lambda x: x[1]):
        print(f"    {s:.3f}  {q}")
    print("\n  OUT-OF-SCOPE (similarity to anchor):")
    for q, s in sorted(zip(questions_out, out_scores), key=lambda x: -x[1]):
        print(f"    {s:.3f}  {q}")
    r = sweep(in_scores, out_scores)
    print("\n  ->", r)
    if not r["clean_gap"]:
        print("  NOTE: in/out distributions overlap — no threshold separates them cleanly.")
        print("        Inspect the borderline questions above; the 'hard negatives'")
        print("        (e.g. mitosis, digestion) reveal whether the anchor is too wide.")


# --- Doc-less anchor: a topic/chapter-level scope description (lean wide, per topic-derivation design) ---
SCOPE_DESCRIPTION = (
    "Photosynthesis in plants: how plants convert light energy into chemical energy. "
    "Covers the light-dependent reactions and the light-independent reactions (the Calvin cycle), "
    "the role of chloroplasts and chlorophyll, absorption of light, the production of ATP and NADPH, "
    "carbon fixation, the conversion of carbon dioxide and water into glucose and oxygen, "
    "and factors affecting the rate of photosynthesis."
)

# --- Doc anchor: a mini 'document' (chunks) on the same topic ---
CHUNKS = [
    "Photosynthesis is the process by which green plants use sunlight to synthesize food from carbon "
    "dioxide and water. It takes place mainly in the leaves, inside organelles called chloroplasts.",
    "The light-dependent reactions occur in the thylakoid membranes. Chlorophyll absorbs light energy, "
    "which is used to split water molecules, releasing oxygen and producing ATP and NADPH.",
    "The Calvin cycle, or light-independent reactions, takes place in the stroma of the chloroplast. "
    "It uses ATP and NADPH to fix carbon dioxide into glucose.",
    "Chlorophyll is the green pigment in plants. It absorbs light most strongly in the blue and red "
    "parts of the spectrum and reflects green light, which is why leaves look green.",
    "The rate of photosynthesis is affected by light intensity, carbon dioxide concentration, and "
    "temperature. Each of these can act as a limiting factor.",
    "During photolysis, water molecules are split using light energy, producing oxygen gas, protons, "
    "and electrons that replace those lost by chlorophyll.",
]

IN_SCOPE = [
    "What happens in the light-dependent reactions?",
    "Why is chlorophyll green?",
    "What is the role of ATP in the Calvin cycle?",
    "How does carbon dioxide get fixed into glucose?",
    "What factors affect the rate of photosynthesis?",
    "Where in the chloroplast does the Calvin cycle happen?",
    "What's the difference between the light and dark reactions?",
    "How do plants produce oxygen?",
    "What is NADPH used for in photosynthesis?",
    "What is photolysis of water?",
    "How is glucose made during photosynthesis?",
    "Why do plants need sunlight?",
]

OUT_OF_SCOPE = [
    "What caused World War 1?",
    "How do I integrate by parts?",
    "What is the capital of Australia?",
    "Explain the French Revolution.",
    "How does a for loop work in Python?",
    "What is mitosis?",  # biology — hard negative
    "How does the human digestive system work?",  # biology — hard negative
    "What's the weather like today?",
    "Who won the World Cup in 2022?",
    "How do I bake sourdough bread?",
    "What is the Pythagorean theorem?",
    "Tell me a joke.",
]


def main():
    desc_anchor = embed([SCOPE_DESCRIPTION], "RETRIEVAL_DOCUMENT")
    chunk_anchor = embed(CHUNKS, "RETRIEVAL_DOCUMENT")
    report("SCOPE_THRESHOLD_DESC  (doc-less: question vs scope description)",
           desc_anchor, IN_SCOPE, OUT_OF_SCOPE, anchor_is_chunkset=False)
    report("SCOPE_THRESHOLD_DOC   (doc session: question vs top-1 chunk)",
           chunk_anchor, IN_SCOPE, OUT_OF_SCOPE, anchor_is_chunkset=True)


if __name__ == "__main__":
    main()
