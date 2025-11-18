from datetime import datetime

from fastapi import FastAPI

# Prefix can be resolved from here if not specified in config.json
ROUTER_PREFIX = "/mock2"

app = FastAPI(title="Mock Router Two")


@app.get("/")
async def root():
    return {
        "router": "mock2",
        "message": "Greetings from mock router two",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/status")
async def status():
    return {"router": "mock2", "status": "green"}

