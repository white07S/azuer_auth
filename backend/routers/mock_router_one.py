from datetime import datetime

from fastapi import APIRouter, FastAPI

# Prefix can be resolved from here if not specified in config.json
ROUTER_PREFIX = "/mock1"

router = APIRouter()


@router.get("/")
async def root():
    return {
        "router": "mock1",
        "message": "Hello from mock router one",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/ping")
async def ping():
    return {"router": "mock1", "status": "ok"}


@router.get("/health")
async def health():
    return {
        "router": "mock1",
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


app = FastAPI(title="Mock Router One")
app.include_router(router)
