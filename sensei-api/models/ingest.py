from pydantic import BaseModel


class UploadResponse(BaseModel):
    status: str
    document_id: str
    session_id: str
    file_name: str
    file_size_bytes: int
    estimated_chunks: int


class CancelRequest(BaseModel):
    document_id: str


class CancelResponse(BaseModel):
    document_id: str
    status: str
