from fastapi import APIRouter, Depends, HTTPException

from dependencies import get_current_user
from models.errors import ErrorDetail
from models.keys import SaveKeyRequest, SaveKeyResponse
from services.encryption import encrypt_key
from services.gemini import validate_key

router = APIRouter(prefix="/keys", tags=["keys"], dependencies=[Depends(get_current_user)])


@router.post("/validate", response_model=SaveKeyResponse)
async def validate(request: SaveKeyRequest) -> SaveKeyResponse:
    if not await validate_key(request.gemini_api_key):
        raise HTTPException(
            status_code=400,
            detail=ErrorDetail(
                code="INVALID_GEMINI_KEY",
                message="This Gemini API key could not be validated.",
            ).model_dump(),
        )
    return SaveKeyResponse(key_ciphertext=encrypt_key(request.gemini_api_key))
