from pydantic import BaseModel


class SaveKeyRequest(BaseModel):
    gemini_api_key: str


class SaveKeyResponse(BaseModel):
    key_ciphertext: str
