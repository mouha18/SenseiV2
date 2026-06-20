from fastapi import APIRouter, Depends

from dependencies import get_current_user

router = APIRouter(prefix="/ingest", tags=["ingest"], dependencies=[Depends(get_current_user)])
