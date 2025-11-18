from datetime import datetime

from fastapi import FastAPI

# Prefix can be resolved from here if not specified in config.json
ROUTER_PREFIX = "/mock1"

app = FastAPI(title="Mock Router One")


@app.get("/")
async def root():
    return {
        "router": "mock1",
        "message": "Hello from mock router one",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/ping")
async def ping():
    return {"router": "mock1", "status": "ok"}

