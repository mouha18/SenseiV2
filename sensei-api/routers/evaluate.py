from fastapi import APIRouter, Depends

from dependencies import get_current_user

router = APIRouter(prefix="/evaluate", tags=["evaluate"], dependencies=[Depends(get_current_user)])
