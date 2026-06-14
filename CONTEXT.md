# Sensei

A Socratic learning assistant: students study their own course materials through guided dialogue grounded in those materials (RAG), and measure their understanding via Feynman-style self-explanation scoring.

## Language

### Keys & Allowance

**BYOK** (Bring Your Own Key):
The mode in which a student supplies their own Gemini API key. Lifts the Daily Allowance entirely — usage is billed to the student. Still subject to the per-minute velocity rate limit.

**Default Key**:
The platform owner's single Gemini API key, held in the FastAPI environment. Used for any student who has not supplied their own key. Spending on it is bounded by the Daily Allowance.
_Avoid_: platform key, fallback key

**Daily Allowance**:
The number of Gemini generation calls a student may make per day on the Default Key (currently 20) — in-scope chat answers and Feynman evaluations both count; out-of-scope redirects and embeddings do not. It counts *delivered answers*, not attempts: a call that returns no usable answer (error, timeout, or safety-block) is refunded and does not count. Exists solely to cap the platform owner's Gemini spend. Does not apply under BYOK.
_Avoid_: quota, daily limit

### Scope

**Scope**:
The single topic a session is locked to (e.g. "World War I"), set once at the first message. Every question after the first is checked against it.
_Avoid_: subject, topic

**Scope derivation**:
The one-time act of determining a session's Scope — from the first question (Gemini draws a label + description) or from uploaded documents. Distinct from Scope enforcement.

**Scope enforcement**:
The per-message check that a question fits the Scope, by embedding similarity against the Scope anchor. Distinct from Scope derivation.

**Scope anchor**:
The reference a question is compared against during Scope enforcement — fixed at the session's **first interaction** and never moved afterward (ADR-0011): the uploaded document chunks if the session began with an upload, otherwise the embedded scope description drawn from the first question. Documents added *later* are retrieval material only and do not change the anchor.

**Out-of-scope upload**:
A document uploaded *after* the Scope is locked that fails the Scope gate (ADR-0011) — rejected, its chunks and raw PDF deleted, with a redirect message. The document analogue of the Out-of-scope redirect. Does **not** count toward the 3-strike `outOfScopeCount`, which is for conversational drift only.

**Out-of-scope redirect**:
The reply when a question fails Scope enforcement — a templated nudge back to the Scope, with no Gemini answer call. Three consecutive prompt the student to start a new session.

### Chat behaviour

**Question modes**:
The three kinds of question Sensei distinguishes when answering — **Factual** (answered directly), **Conceptual** and **Application** (answered Socratically, with a guiding question first).

**Response modes**:
How Sensei replies — **Socratic** (a guiding question), **Direct** (a straight answer), or **Redirect** (an Out-of-scope nudge).

### Feynman

**Feynman evaluation**:
A mode where the student explains a concept in their own words and receives a 0–100 score across the 7C's with per-criterion criticism. Named for the Feynman technique — you understand something only if you can explain it simply.

**7C's**:
The seven criteria a Feynman explanation is scored on — Clear, Concise, Concrete, Correct, Coherent, Complete, Courteous. Correct and Complete are judged against the student's own material when documents exist, otherwise scoped general knowledge.
