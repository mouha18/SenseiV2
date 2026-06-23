from dataclasses import dataclass

from services.gemini import FeynmanRawScores, score_feynman_explanation

# The six understanding criteria — Courteous is scored and shown as feedback
# but excluded from the overall (tone isn't mastery, ADR-0007).
UNDERSTANDING_CRITERIA = ("clear", "concise", "concrete", "correct", "coherent", "complete")
RETRY_THRESHOLD = 70


@dataclass
class ScoredFeynman:
    scores: FeynmanRawScores
    overall_score: int
    retry_suggested: bool
    summary: str


async def score_explanation(
    *,
    concept: str,
    explanation: str,
    reference_material: str | None,
    api_key: str,
) -> ScoredFeynman:
    """Grades a Feynman explanation (PROMPTS.md §4). Gemini emits only the
    seven per-criterion {score, criticism} pairs; overall_score and
    retry_suggested are deterministic functions of the sub-scores, kept in
    code so they're transparent and tamper-proof (ADR-0007 division of
    labour) — neither is emitted by Gemini.
    """
    scores = await score_feynman_explanation(
        concept=concept,
        explanation=explanation,
        reference_material=reference_material,
        api_key=api_key,
    )
    understanding_scores = (
        scores["clear"]["score"],
        scores["concise"]["score"],
        scores["concrete"]["score"],
        scores["correct"]["score"],
        scores["coherent"]["score"],
        scores["complete"]["score"],
    )
    overall_score = round(sum(understanding_scores) / len(understanding_scores))
    return ScoredFeynman(
        scores=scores,
        overall_score=overall_score,
        retry_suggested=overall_score < RETRY_THRESHOLD,
        summary=scores["summary"],
    )
