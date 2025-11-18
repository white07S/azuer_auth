from datetime import datetime

from fastapi import APIRouter, FastAPI

# Prefix can be resolved from here if not specified in config.json
ROUTER_PREFIX = "/mock2"

router = APIRouter()


@router.get("/")
async def root():
    return {
        "router": "mock2",
        "message": "Greetings from mock router two",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/status")
async def status():
    return {"router": "mock2", "status": "green"}


@router.get("/health")
async def health():
    return {
        "router": "mock2",
        "status": "green",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


app = FastAPI(title="Mock Router Two")
app.include_router(router)
