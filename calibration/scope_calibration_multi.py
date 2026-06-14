"""
Multi-topic scope-threshold calibration (ADR-0004). Throwaway.

Extends scope_calibration.py across 4 subjects (biology, history, math, CS) to
test whether ONE global threshold separates in-/out-of-scope across topics —
the real requirement, since thresholds can't be tuned per session.

For each topic, out-of-scope = its own same-domain hard negatives
+ every other topic's in-scope questions (cross-domain) + generic off-topic.

Run:
    GEMINI_API_KEY=... calibration/.venv/Scripts/python.exe calibration/scope_calibration_multi.py
"""

import os
import numpy as np
from google import genai
from google.genai import types

MODEL = "gemini-embedding-001"
DIM = 1536
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def embed(texts, task_type):
    out = []
    for i in range(0, len(texts), 100):
        resp = client.models.embed_content(
            model=MODEL, contents=texts[i : i + 100],
            config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=DIM),
        )
        out.extend(e.values for e in resp.embeddings)
    v = np.array(out, dtype=np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return v


TOPICS = {
    "Photosynthesis (biology)": {
        "description": (
            "Photosynthesis in plants: how plants convert light energy into chemical energy. "
            "Covers the light-dependent and light-independent reactions (the Calvin cycle), chloroplasts "
            "and chlorophyll, ATP and NADPH, carbon fixation, the conversion of carbon dioxide and water "
            "into glucose and oxygen, and factors affecting the rate of photosynthesis."
        ),
        "chunks": [
            "Photosynthesis is the process by which green plants use sunlight to synthesize food from carbon dioxide and water, mainly in the leaves inside chloroplasts.",
            "The light-dependent reactions occur in the thylakoid membranes; chlorophyll absorbs light, which splits water, releasing oxygen and producing ATP and NADPH.",
            "The Calvin cycle, in the stroma, uses ATP and NADPH to fix carbon dioxide into glucose.",
            "Chlorophyll absorbs blue and red light and reflects green, which is why leaves look green.",
            "The rate of photosynthesis is affected by light intensity, carbon dioxide concentration, and temperature.",
            "During photolysis, water is split using light energy, producing oxygen, protons, and electrons.",
        ],
        "in_scope": [
            "What happens in the light-dependent reactions?", "Why is chlorophyll green?",
            "What is the role of ATP in the Calvin cycle?", "How does carbon dioxide get fixed into glucose?",
            "What factors affect the rate of photosynthesis?", "Where in the chloroplast does the Calvin cycle happen?",
            "How do plants produce oxygen?", "What is NADPH used for in photosynthesis?",
            "What is photolysis of water?", "How is glucose made during photosynthesis?",
        ],
        "near_off": [  # same domain (biology), different topic
            "What is mitosis?", "How does the human digestive system work?", "How does DNA replication work?",
        ],
    },
    "French Revolution (history)": {
        "description": (
            "The French Revolution (1789-1799): causes, key events, and consequences. Covers the financial "
            "crisis and inequality of the Ancien Regime, the Estates-General and National Assembly, the storming "
            "of the Bastille, the Declaration of the Rights of Man, the abolition of the monarchy, the Reign of "
            "Terror and Robespierre, factions such as the Jacobins, and the rise of Napoleon."
        ),
        "chunks": [
            "The French Revolution began in 1789, driven by discontent with the Ancien Regime, a financial crisis, and heavy taxation falling on the common people while clergy and nobility paid little.",
            "In 1789 the Estates-General convened, and the Third Estate broke away to form the National Assembly, vowing in the Tennis Court Oath not to disband until France had a constitution.",
            "On 14 July 1789 a Parisian crowd stormed the Bastille, a royal fortress and prison, a symbolic event still marked as Bastille Day.",
            "The Declaration of the Rights of Man and of the Citizen, adopted in 1789, proclaimed liberty, equality, and fraternity.",
            "The Reign of Terror, led by Robespierre and the Committee of Public Safety, executed thousands by guillotine between 1793 and 1794.",
            "After years of instability, Napoleon Bonaparte seized power in 1799, ending the revolutionary period.",
        ],
        "in_scope": [
            "What caused the French Revolution?", "What was the storming of the Bastille?",
            "Who was Robespierre?", "What was the Reign of Terror?",
            "What did the Declaration of the Rights of Man say?", "Why did the Third Estate form the National Assembly?",
            "What was the Ancien Regime?", "How did Napoleon come to power?",
            "What happened at the Estates-General?", "What is Bastille Day?",
        ],
        "near_off": [  # same domain (history), different topic
            "What caused the American Revolution?", "What started World War 1?", "What was the Russian Revolution?",
        ],
    },
    "Derivatives (calculus)": {
        "description": (
            "Derivatives in differential calculus: the derivative as instantaneous rate of change and the slope "
            "of a tangent line. Covers limits and the definition of the derivative, differentiation rules "
            "(power, product, quotient, chain), derivatives of common functions, higher-order derivatives, and "
            "applications such as finding maxima and minima."
        ),
        "chunks": [
            "The derivative of a function measures the instantaneous rate of change with respect to its variable; geometrically it is the slope of the tangent line at a point.",
            "The derivative is defined as the limit of the difference quotient: f'(x) = lim(h->0) [f(x+h) - f(x)] / h.",
            "The power rule states that the derivative of x^n is n*x^(n-1).",
            "The chain rule differentiates composite functions: if y = f(g(x)), then dy/dx = f'(g(x)) * g'(x).",
            "The product rule gives (uv)' = u'v + uv'; the quotient rule handles a ratio of two functions.",
            "Derivatives find maxima and minima: at a local maximum or minimum the first derivative is zero.",
        ],
        "in_scope": [
            "What is the derivative of a function?", "How do you use the chain rule?",
            "What is the power rule?", "How is the derivative defined using limits?",
            "How do you find the maximum of a function using derivatives?", "What does the derivative represent geometrically?",
            "How do you differentiate a product of two functions?", "How do you find the slope of a tangent line?",
            "What is the quotient rule?", "How do you differentiate a composite function?",
        ],
        "near_off": [  # same domain (math), different topic
            "How do you integrate a function?", "How do you multiply two matrices?", "What is the Pythagorean theorem?",
        ],
    },
    "HTTP and the web (CS)": {
        "description": (
            "How the web and HTTP work: the protocol browsers and servers use to communicate. Covers HTTP "
            "requests and responses, methods like GET and POST, status codes, headers, the client-server model, "
            "URLs and DNS, the difference between HTTP and HTTPS, and cookies and sessions."
        ),
        "chunks": [
            "HTTP, the Hypertext Transfer Protocol, is used by web browsers and servers to communicate: a client sends a request and the server returns a response.",
            "An HTTP request includes a method such as GET (retrieve data) or POST (send data), a URL, and headers carrying metadata.",
            "HTTP status codes indicate the result: 200 means success, 404 means not found, 500 means a server error.",
            "HTTPS is HTTP secured with TLS encryption, so data between browser and server cannot be read by third parties.",
            "When you type a URL, DNS translates the domain name into an IP address so the browser knows which server to contact.",
            "Cookies are small pieces of data stored by the browser and sent with requests, often used to keep a user logged in.",
        ],
        "in_scope": [
            "What is HTTP?", "What is the difference between GET and POST?",
            "What does a 404 status code mean?", "How is HTTPS different from HTTP?",
            "What does DNS do?", "What are HTTP headers?",
            "How do cookies keep me logged in?", "What is the client-server model?",
            "What happens when I type a URL into a browser?", "Why is HTTPS secure?",
        ],
        "near_off": [  # same domain (CS), different topic
            "How does a CPU work?", "What is a database index?", "How does a for loop work in Python?",
        ],
    },
}

GENERIC_OFF = [
    "What's the weather like today?", "Tell me a joke.", "Who won the World Cup in 2022?",
    "How do I bake sourdough bread?", "What is the capital of Australia?",
]


def main():
    names = list(TOPICS.keys())

    # Embed every question once (RETRIEVAL_QUERY), reuse across topics.
    qcache = {}
    all_qs = list({q for t in TOPICS.values() for q in t["in_scope"] + t["near_off"]} | set(GENERIC_OFF))
    qvecs = embed(all_qs, "RETRIEVAL_QUERY")
    for q, v in zip(all_qs, qvecs):
        qcache[q] = v

    # Embed anchors (RETRIEVAL_DOCUMENT).
    desc_vecs = embed([TOPICS[n]["description"] for n in names], "RETRIEVAL_DOCUMENT")
    desc_anchor = {n: desc_vecs[i] for i, n in enumerate(names)}
    chunk_anchor = {n: embed(TOPICS[n]["chunks"], "RETRIEVAL_DOCUMENT") for n in names}

    for mode in ("DESC", "DOC"):
        print(f"\n{'#' * 72}\n# {mode}  ({'question vs description' if mode=='DESC' else 'question vs top-1 chunk'})\n{'#' * 72}")
        global_min_in, global_min_in_q = 1.0, None
        global_max_out, global_max_out_q = 0.0, None

        for n in names:
            if mode == "DESC":
                A = desc_anchor[n][None, :]  # (1, d)
            else:
                A = chunk_anchor[n]          # (k, d)

            def score(q):
                return float((A @ qcache[q]).max())

            in_s = [(q, score(q)) for q in TOPICS[n]["in_scope"]]
            out_qs = TOPICS[n]["near_off"] + \
                     [q for m in names if m != n for q in TOPICS[m]["in_scope"]] + GENERIC_OFF
            out_s = [(q, score(q)) for q in out_qs]

            min_in_q, min_in = min(in_s, key=lambda x: x[1])
            max_out_q, max_out = max(out_s, key=lambda x: x[1])
            gap = min_in - max_out
            print(f"\n  {n}")
            print(f"    min in-scope : {min_in:.3f}   ({min_in_q})")
            print(f"    max out      : {max_out:.3f}   ({max_out_q})")
            print(f"    per-topic gap: {gap:+.3f}   {'CLEAN' if gap > 0 else 'OVERLAP'}")

            if min_in < global_min_in:
                global_min_in, global_min_in_q = min_in, f"{n}: {min_in_q}"
            if max_out > global_max_out:
                global_max_out, global_max_out_q = max_out, f"{n}: {max_out_q}"

        clean = global_min_in > global_max_out
        print(f"\n  {'-'*60}")
        print(f"  GLOBAL  min in-scope = {global_min_in:.3f}  [{global_min_in_q}]")
        print(f"  GLOBAL  max out      = {global_max_out:.3f}  [{global_max_out_q}]")
        print(f"  GLOBAL  gap          = {global_min_in - global_max_out:+.3f}  -> {'ONE THRESHOLD WORKS' if clean else 'NO SINGLE THRESHOLD SEPARATES ALL TOPICS'}")
        if clean:
            print(f"  GLOBAL  midpoint     = {(global_min_in + global_max_out)/2:.3f}")
            print(f"  lean-wide pick (just above global max-out) ~ {global_max_out + 0.01:.3f}")


if __name__ == "__main__":
    main()
