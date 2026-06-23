from pydantic import BaseModel


class CleanupSessionRequest(BaseModel):
    session_id: str
    user_id: str
    storage_paths: list[str]


class CleanupSessionResponse(BaseModel):
    session_id: str
    deleted: bool
