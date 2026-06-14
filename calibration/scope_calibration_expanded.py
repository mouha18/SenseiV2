"""
Expanded scope-threshold calibration (ADR-0004) — pre-launch confidence pass.

8 topics including 3 SAME-DOMAIN PAIRS (the case DESC struggled with):
  biology:  photosynthesis  /  cellular respiration
  history:  french revolution  /  world war II
  math:     derivatives  /  linear algebra
  + HTTP (CS) and supply & demand (economics).
Questions mix full and terse/colloquial phrasings to approximate real students.

Validates two things against the current numbers:
  DOC  : does SCOPE_THRESHOLD_DOC = 0.64 still cleanly separate in/out across all 8?
  DESC : with band [0.57, 0.63] — are there CLEAR-ZONE ERRORS (in-scope <=0.57, or
         out-of-scope >=0.63)? Those are the unforgivable ones (the judge never sees
         them). Also reports borderline-band load (= how often the judge fires).

Key handling: put `GEMINI_API_KEY=...` in calibration/.env (gitignored). Never on the CLI.
Run: calibration/.venv/Scripts/python.exe calibration/scope_calibration_expanded.py
"""

import os
import time
from pathlib import Path
import numpy as np

# --- load key from .env so it never touches the shell / transcript ---
_envf = Path(__file__).parent / ".env"
if _envf.exists():
    for line in _envf.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from google import genai
from google.genai import types

MODEL, DIM = "gemini-embedding-001", 1536
DOC_BAND_LOW, DOC_BAND_HIGH = 0.59, 0.66
BAND_LOW, BAND_HIGH = 0.57, 0.63
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

_req = []
def embed(texts, task_type, max_per_min=80, batch=10):
    out = []
    for i in range(0, len(texts), batch):
        chunk = texts[i : i + batch]
        now = time.time()
        while _req and now - _req[0] > 60:
            _req.pop(0)
        if _req and len(_req) + len(chunk) > max_per_min:
            wait = 61 - (now - _req[0])
            if wait > 0:
                print(f"    ...pause {wait:.0f}s"); time.sleep(wait); _req.clear()
        for _ in range(6):
            try:
                r = client.models.embed_content(model=MODEL, contents=chunk,
                    config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=DIM))
                break
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    print("    ...429, backing off 50s"); time.sleep(50); _req.clear()
                else:
                    raise
        else:
            raise RuntimeError("repeated 429s")
        out.extend(e.values for e in r.embeddings)
        _req.extend([time.time()] * len(chunk))
    v = np.array(out, dtype=np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return v


TOPICS = {
    "Photosynthesis": {
        "description": "Photosynthesis in plants: converting light energy into chemical energy. Light-dependent and light-independent (Calvin cycle) reactions, chloroplasts, chlorophyll, ATP and NADPH, carbon fixation, producing glucose and oxygen, and factors affecting the rate.",
        "chunks": [
            "Photosynthesis lets green plants make food from carbon dioxide and water using sunlight, in chloroplasts.",
            "Light-dependent reactions in the thylakoids split water, release oxygen, and make ATP and NADPH.",
            "The Calvin cycle in the stroma uses ATP and NADPH to fix carbon dioxide into glucose.",
            "Chlorophyll absorbs red and blue light and reflects green; rate depends on light, CO2, and temperature.",
        ],
        "in_scope": ["What happens in the light-dependent reactions?", "Why is chlorophyll green?",
            "role of ATP in the Calvin cycle?", "how do plants make oxygen", "what affects photosynthesis rate",
            "What is photolysis?", "calvin cycle?", "How is glucose made in photosynthesis?",
            "why do plants need light", "what is NADPH for"],
    },
    "Cellular respiration": {
        "description": "Cellular respiration: how cells release energy from glucose. Glycolysis, the Krebs (citric acid) cycle, the electron transport chain, the role of mitochondria, oxygen as the final electron acceptor, and ATP production; aerobic vs anaerobic respiration.",
        "chunks": [
            "Cellular respiration breaks down glucose to release energy as ATP, mostly in the mitochondria.",
            "Glycolysis splits glucose into pyruvate in the cytoplasm, making a small amount of ATP.",
            "The Krebs cycle and electron transport chain produce most ATP, using oxygen as the final electron acceptor.",
            "Anaerobic respiration occurs without oxygen and yields far less ATP, producing lactate or ethanol.",
        ],
        "in_scope": ["What is glycolysis?", "where does the Krebs cycle happen", "role of mitochondria in respiration",
            "how is ATP made in cells", "aerobic vs anaerobic respiration?", "what is the electron transport chain",
            "why do cells need oxygen", "what happens to glucose in respiration", "krebs cycle?", "what is pyruvate"],
    },
    "French Revolution": {
        "description": "The French Revolution (1789-1799): causes and events. The Ancien Regime and inequality, the Estates-General and National Assembly, the storming of the Bastille, the Declaration of the Rights of Man, the fall of the monarchy, the Reign of Terror and Robespierre, the Jacobins, and the rise of Napoleon.",
        "chunks": [
            "The French Revolution began in 1789 amid financial crisis and resentment of the Ancien Regime.",
            "The Third Estate formed the National Assembly; a crowd stormed the Bastille on 14 July 1789.",
            "The Declaration of the Rights of Man proclaimed liberty, equality, and fraternity.",
            "The Reign of Terror under Robespierre executed thousands; Napoleon seized power in 1799.",
        ],
        "in_scope": ["What caused the French Revolution?", "storming of the Bastille?", "who was Robespierre",
            "what was the Reign of Terror", "what did the Declaration of the Rights of Man say",
            "why did the Third Estate revolt", "what was the Ancien Regime", "how did Napoleon take power",
            "what is Bastille Day", "who were the Jacobins"],
    },
    "World War II": {
        "description": "World War II (1939-1945): causes, major events, and outcomes. The rise of Nazi Germany, the invasion of Poland, the Holocaust, major theatres in Europe and the Pacific, key battles like Stalingrad and D-Day, the Allied and Axis powers, and the use of atomic bombs ending the war.",
        "chunks": [
            "World War II began in 1939 when Germany invaded Poland, drawing in the Allies against the Axis.",
            "The Holocaust was the systematic genocide of six million Jews by Nazi Germany.",
            "Turning points included the Battle of Stalingrad and the D-Day landings in Normandy in 1944.",
            "The war ended in 1945 after the atomic bombings of Hiroshima and Nagasaki.",
        ],
        "in_scope": ["What started World War 2?", "what was D-Day", "who were the Axis powers",
            "what was the Holocaust", "what happened at Stalingrad", "why did Germany invade Poland",
            "how did WW2 end", "what were the atomic bombings", "what was the Battle of Britain", "who was Hitler"],
    },
    "Derivatives": {
        "description": "Derivatives in differential calculus: the derivative as instantaneous rate of change and slope of a tangent. Limits and the definition of the derivative, differentiation rules (power, product, quotient, chain), derivatives of common functions, and finding maxima and minima.",
        "chunks": [
            "The derivative measures instantaneous rate of change; geometrically it is the slope of the tangent line.",
            "It is defined as the limit of the difference quotient as h approaches zero.",
            "The power rule: the derivative of x^n is n*x^(n-1); the chain rule differentiates composite functions.",
            "Setting the first derivative to zero locates maxima and minima of a function.",
        ],
        "in_scope": ["What is a derivative?", "how does the chain rule work", "what is the power rule",
            "derivative definition with limits?", "how to find a maximum using derivatives",
            "what does a derivative mean geometrically", "how to differentiate a product",
            "slope of a tangent line?", "what is the quotient rule", "derivative of x squared"],
    },
    "Linear algebra": {
        "description": "Linear algebra: vectors and matrices. Matrix addition and multiplication, the determinant, the inverse of a matrix, solving systems of linear equations, vector spaces, eigenvalues and eigenvectors, and linear transformations.",
        "chunks": [
            "Linear algebra studies vectors, matrices, and linear transformations between vector spaces.",
            "Matrices can be added and multiplied; matrix multiplication combines rows with columns.",
            "The determinant indicates whether a matrix is invertible; the inverse undoes the transformation.",
            "Eigenvalues and eigenvectors describe directions a linear transformation only scales.",
        ],
        "in_scope": ["How do you multiply two matrices?", "what is a determinant", "what is an eigenvalue",
            "how to find a matrix inverse", "how to solve a system of linear equations",
            "what is a vector space", "what is a linear transformation", "what are eigenvectors",
            "matrix multiplication?", "when is a matrix invertible"],
    },
    "HTTP and the web": {
        "description": "How the web and HTTP work: the protocol browsers and servers use to communicate. HTTP requests and responses, GET and POST methods, status codes, headers, the client-server model, URLs and DNS, HTTP vs HTTPS, and cookies and sessions.",
        "chunks": [
            "HTTP lets browsers and servers communicate: a client sends a request, the server returns a response.",
            "Requests use methods like GET (retrieve) and POST (send), with a URL and headers.",
            "Status codes signal results: 200 success, 404 not found, 500 server error; HTTPS adds TLS encryption.",
            "DNS maps domain names to IP addresses; cookies store data to keep a user logged in.",
        ],
        "in_scope": ["What is HTTP?", "difference between GET and POST", "what does a 404 mean",
            "how is HTTPS different", "what does DNS do", "what are HTTP headers",
            "how do cookies work", "what is the client-server model", "what happens when I type a URL",
            "why is https secure"],
    },
    "Supply and demand": {
        "description": "Supply and demand in economics: how prices are set in a market. The law of demand and the law of supply, the demand and supply curves, market equilibrium, shifts in supply and demand, surplus and shortage, and the effect of price on quantity.",
        "chunks": [
            "Supply and demand determine the market price of a good at the point where they balance.",
            "The law of demand says quantity demanded falls as price rises; the law of supply says supply rises with price.",
            "Equilibrium is the price where quantity supplied equals quantity demanded.",
            "A price above equilibrium causes a surplus; a price below it causes a shortage.",
        ],
        "in_scope": ["What is the law of demand?", "what is market equilibrium", "what causes a shortage",
            "how is price determined in a market", "what shifts a demand curve", "what is a surplus",
            "law of supply?", "what is the demand curve", "why does demand fall when price rises",
            "what happens at equilibrium"],
    },
}

GENERIC_OFF = ["what's the weather", "tell me a joke", "who won the world cup",
               "how do I bake bread", "capital of australia", "recommend a movie"]


def main():
    names = list(TOPICS.keys())
    all_qs = list({q for t in TOPICS.values() for q in t["in_scope"]} | set(GENERIC_OFF))
    qv = {q: v for q, v in zip(all_qs, embed(all_qs, "RETRIEVAL_QUERY"))}
    desc = {n: v for n, v in zip(names, embed([TOPICS[n]["description"] for n in names], "RETRIEVAL_DOCUMENT"))}
    chunks = {n: embed(TOPICS[n]["chunks"], "RETRIEVAL_DOCUMENT") for n in names}

    # ---- DOC: clear-zone errors + judge load with band [0.59, 0.66] ----
    print("\n" + "#" * 72 + f"\n# DOC  (top-1 chunk vs description; band [{DOC_BAND_LOW}, {DOC_BAND_HIGH}])\n" + "#" * 72)
    clear_err, band_in, band_out, n_in, n_out = [], 0, 0, 0, 0
    for n in names:
        for q in TOPICS[n]["in_scope"]:
            s = float((chunks[n] @ qv[q]).max()); n_in += 1
            if s <= DOC_BAND_LOW:
                clear_err.append(f"CLEAR-ZONE: in-scope landed OUT  {s:.3f}  [{n}] {q}")
            elif s < DOC_BAND_HIGH:
                band_in += 1
        out_qs = [q for m in names if m != n for q in TOPICS[m]["in_scope"]] + GENERIC_OFF
        for q in out_qs:
            s = float((chunks[n] @ qv[q]).max()); n_out += 1
            if s >= DOC_BAND_HIGH:
                clear_err.append(f"CLEAR-ZONE: out-scope landed IN  {s:.3f}  [{n}] {q}")
            elif s > DOC_BAND_LOW:
                band_out += 1
    print(f"  clear-zone errors (judge never sees these) -> {'NONE' if not clear_err else str(len(clear_err)) + ':'}")
    for e in clear_err[:30]:
        print("    " + e)
    print(f"  borderline band load: {band_in}/{n_in} in-scope and {band_out}/{n_out} out-of-scope "
          f"questions hit the judge ({100*(band_in+band_out)/(n_in+n_out):.0f}% of messages)")

    # ---- DESC: clear-zone errors + judge load with band [0.57, 0.63] ----
    print("\n" + "#" * 72 + f"\n# DESC  (vs description; band [{BAND_LOW}, {BAND_HIGH}])\n" + "#" * 72)
    clear_err, band_in, band_out, n_in, n_out = [], 0, 0, 0, 0
    for n in names:
        for q in TOPICS[n]["in_scope"]:
            s = float(desc[n] @ qv[q]); n_in += 1
            if s <= BAND_LOW:
                clear_err.append(f"CLEAR-ZONE: in-scope landed OUT  {s:.3f}  [{n}] {q}")
            elif s < BAND_HIGH:
                band_in += 1
        out_qs = [q for m in names if m != n for q in TOPICS[m]["in_scope"]] + GENERIC_OFF
        for q in out_qs:
            s = float(desc[n] @ qv[q]); n_out += 1
            if s >= BAND_HIGH:
                clear_err.append(f"CLEAR-ZONE: out-scope landed IN  {s:.3f}  [{n}] {q}")
            elif s > BAND_LOW:
                band_out += 1
    print(f"  clear-zone errors (judge never sees these) -> {'NONE' if not clear_err else str(len(clear_err)) + ':'}")
    for e in clear_err[:30]:
        print("    " + e)
    print(f"  borderline band load: {band_in}/{n_in} in-scope and {band_out}/{n_out} out-of-scope "
          f"questions hit the judge ({100*(band_in+band_out)/(n_in+n_out):.0f}% of messages)")


if __name__ == "__main__":
    main()
