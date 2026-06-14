# Scope-threshold calibration spike

**Throwaway.** Not part of the app — delete it once the thresholds are set. Its only job is to turn ADR-0004's two scope thresholds from guesses into measured numbers, against the real embedding model (`gemini-embedding-001`, 1536-dim).

## Why this exists

ADR-0004 gates every chat message by embedding it and comparing cosine similarity to a scope **anchor** against a threshold:
- **`SCOPE_THRESHOLD_DESC`** — doc-less sessions: question vs the embedded scope *description*.
- **`SCOPE_THRESHOLD_DOC`** — doc sessions: question vs the *top-1 chunk* similarity.

These sit in different score distributions, so each is calibrated separately (ADR-0004). You can't pick them on paper — you measure where in-scope and out-of-scope questions separate.

## Run

```bash
pip install google-genai numpy
# PowerShell:  $env:GEMINI_API_KEY="your-key"
# bash:        export GEMINI_API_KEY=your-key
python scope_calibration.py
```

(Use the platform Default Key or any Gemini key — embeddings are cheap.)

## Reading the output

For each threshold it prints every sample question with its similarity to the anchor (sorted), then a summary:
- `suggested_threshold` — the cutoff that best separates the labeled in/out sets here.
- `clean_gap` — `true` if every in-scope question scored above every out-of-scope one (a clean margin). If `false`, the groups overlap and *no* single cutoff is perfect — look at the borderline questions.
- `min_in_scope` / `max_out_of_scope` / `midpoint_if_separable` — the margin and its midpoint.

**Pick a threshold inside the gap, leaning slightly low** (toward `max_out_of_scope`) — consistent with the product decision to lean wide and avoid falsely rejecting legitimate study questions. The **hard negatives** (`mitosis`, `digestive system` — biology but off-topic) are the interesting ones: if they score near the in-scope band, the anchor is too broad.

## Important caveats

- **The samples here use one topic (photosynthesis).** Thresholds should generalize across topics, so before locking, **swap in 2–3 other subjects** (a humanities topic, a math topic, a CS topic) and confirm the same cutoff still separates them. A threshold tuned on one topic can mislead.
- **Task types matter.** The script embeds the anchor as `RETRIEVAL_DOCUMENT` and questions as `RETRIEVAL_QUERY` to mirror production. Keep `embedder.py`/`retriever.py` consistent with that, or the calibrated numbers won't transfer.
- **MRL normalization.** At 1536 dims (not the 3072 default) the vectors must be L2-normalized before cosine — the script does this; production must too.
- **Doc-gate threshold (ADR-0011)** — the *document*-level gate (median/quorum of a chunk sample vs the anchor) is a third, separate threshold not covered here. Calibrate it once the ingestion pipeline exists, since it compares chunk-samples, not questions.
- If the `google-genai` embed call signature has drifted since this was written, adjust `embed()` — the SDK surface, not the method, is the only fragile part.

## Where the result goes

Record the two numbers in ADR-0004 (replacing the symbolic `SCOPE_THRESHOLD_DESC` / `SCOPE_THRESHOLD_DOC`) and in `config.py` when the backend is built. Then this folder can go.
