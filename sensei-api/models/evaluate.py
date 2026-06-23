from pydantic import BaseModel


class SuggestionsRequest(BaseModel):
    session_id: str


class SuggestionsResponse(BaseModel):
    suggestions: list[str]


class FeynmanRequest(BaseModel):
    session_id: str
    concept: str
    explanation: str


class FeynmanScores(BaseModel):
    clear: int
    concise: int
    concrete: int
    correct: int
    coherent: int
    complete: int
    courteous: int


class FeynmanCriticism(BaseModel):
    clear: str
    concise: str
    concrete: str
    correct: str
    coherent: str
    complete: str
    courteous: str


class FeynmanResponse(BaseModel):
    concept: str
    overall_score: int
    scores: FeynmanScores
    criticism: FeynmanCriticism
    summary: str
    retry_suggested: bool
