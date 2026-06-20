from fastapi import APIRouter, Depends

from dependencies import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(get_current_user)])
