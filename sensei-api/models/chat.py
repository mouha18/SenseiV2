from pydantic import BaseModel


class ChatRequest(BaseModel):
    session_id: str
    question: str


class ChatResponse(BaseModel):
    answer: str
    response_type: str
    source: str | None
    chunks_used: int
    out_of_scope: bool
    new_session_required: bool
