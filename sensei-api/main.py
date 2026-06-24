from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from models.health import HealthResponse
from routers import chat, evaluate, ingest, internal, keys

settings = get_settings()

app = FastAPI(title="Sensei API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


app.include_router(ingest.router)
app.include_router(chat.router)
app.include_router(evaluate.router)
app.include_router(keys.router)
app.include_router(internal.router)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version="1.0.0")


@app.get("/debug/cors")
async def debug_cors() -> dict:
    return {"allowed_origins": settings.allowed_origins_list}


@app.get("/debug/config")
async def debug_config() -> dict:
    return {
        "convex_url": repr(settings.CONVEX_URL),
        "convex_site_url": repr(settings.CONVEX_SITE_URL),
        "allowed_origins": settings.allowed_origins_list,
    }
