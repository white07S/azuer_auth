"""
Main router entrypoint.

This process:
- Reads router definitions from routers/config.json
- Starts each router as its own uvicorn process
- Runs a FastAPI gateway that proxies requests to routers based on path prefix
"""
import importlib
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
import uvicorn

BASE_DIR = Path(__file__).resolve().parent
ROUTERS_CONFIG_PATH = BASE_DIR / "routers" / "config.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("main-router")


def _load_router_config() -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Load main router and child router configuration from JSON."""
    if not ROUTERS_CONFIG_PATH.exists():
        raise RuntimeError(f"Router config not found at {ROUTERS_CONFIG_PATH}")

    with ROUTERS_CONFIG_PATH.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    main_cfg: Dict[str, Any] = raw.get("main", {})
    main_cfg.setdefault("host", "0.0.0.0")
    main_cfg.setdefault("port", 8000)
    # Main router workers – typically 4–5 as requested.
    main_cfg.setdefault("workers", 4)
    main_cfg.setdefault("reload", False)
    main_cfg.setdefault("log_level", "info")

    routers: List[Dict[str, Any]] = []
    for entry in raw.get("routers", []):
        if "name" not in entry or "router_path" not in entry or "port" not in entry:
            raise RuntimeError(
                "Each router entry must have at least 'name', 'router_path', and 'port'"
            )

        router = dict(entry)
        router.setdefault("host", "127.0.0.1")
        # Prefix can be overridden in config or resolved from router code.
        router.setdefault("prefix", "")
        routers.append(router)

    if not routers:
        raise RuntimeError("No router entries found in router configuration")

    return main_cfg, routers


def _normalise_prefix(prefix: Optional[str]) -> str:
    """Normalise a router prefix to a clean path fragment."""
    if not prefix:
        return ""
    if not prefix.startswith("/"):
        prefix = "/" + prefix
    if prefix != "/":
        prefix = prefix.rstrip("/")
    return prefix


def _ensure_router_prefix(router_cfg: Dict[str, Any]) -> None:
    """
    Ensure router_cfg['prefix'] is set.

    If not provided in config, attempt to read ROUTER_PREFIX from the router module.
    """
    if router_cfg.get("prefix"):
        router_cfg["prefix"] = _normalise_prefix(str(router_cfg["prefix"]))
        return

    module_path, _, _ = router_cfg["router_path"].partition(":")
    try:
        module = importlib.import_module(module_path)
        prefix = getattr(module, "ROUTER_PREFIX", "/")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "Failed to import router module %s to resolve prefix: %s",
            module_path,
            exc,
        )
        prefix = "/"

    router_cfg["prefix"] = _normalise_prefix(prefix)


MAIN_CONFIG, ROUTER_CONFIGS = _load_router_config()

for router_cfg in ROUTER_CONFIGS:
    _ensure_router_prefix(router_cfg)

ROUTER_PROCESSES: Dict[str, subprocess.Popen] = {}


def _start_router_process(router_cfg: Dict[str, Any]) -> None:
    """Start a single router as a separate uvicorn process."""
    name = router_cfg["name"]
    if name in ROUTER_PROCESSES and ROUTER_PROCESSES[name].poll() is None:
        # Already running
        return

    host = router_cfg.get("host", "127.0.0.1")
    port = str(router_cfg["port"])
    router_path = router_cfg["router_path"]

    extra_args = router_cfg.get("uvicorn_args", [])

    cmd: List[str] = [
        sys.executable,
        "-m",
        "uvicorn",
        router_path,
        "--host",
        host,
        "--port",
        port,
        "--log-level",
        router_cfg.get("log_level", "info"),
    ]

    # Allow additional uvicorn CLI arguments via config.
    if isinstance(extra_args, str):
        cmd.extend(extra_args.split())
    elif isinstance(extra_args, list):
        cmd.extend(str(x) for x in extra_args)

    logger.info(
        "Starting router %s on %s:%s (%s)", name, host, port, router_path
    )
    process = subprocess.Popen(
        cmd,
        cwd=str(BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    ROUTER_PROCESSES[name] = process


def start_all_routers() -> None:
    """Start all configured routers."""
    for router_cfg in ROUTER_CONFIGS:
        _start_router_process(router_cfg)


def stop_all_routers() -> None:
    """Terminate all router processes."""
    for name, process in ROUTER_PROCESSES.items():
        if process.poll() is None:
            logger.info("Stopping router %s (pid=%s)", name, process.pid)
            process.terminate()

    for name, process in ROUTER_PROCESSES.items():
        if process.poll() is None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Killing router %s (pid=%s)", name, process.pid)
                process.kill()

    ROUTER_PROCESSES.clear()


def wait_for_routers_ready(timeout: float = 30.0, interval: float = 0.5) -> None:
    """
    Block until all routers respond successfully on /health or timeout.

    Raises RuntimeError if any router fails to become healthy in time.
    """
    pending: Dict[str, Dict[str, Any]] = {
        r["name"]: r for r in ROUTER_CONFIGS
    }
    deadline = time.time() + timeout

    with httpx.Client() as client:
        while pending and time.time() < deadline:
            for name in list(pending.keys()):
                cfg = pending[name]
                url = f"http://{cfg.get('host', '127.0.0.1')}:{cfg['port']}/health"
                try:
                    resp = client.get(url, timeout=2.0)
                    if resp.status_code == 200:
                        logger.info("Router %s passed health check", name)
                        pending.pop(name, None)
                except Exception as exc:
                    logger.debug(
                        "Router %s health check failed: %s",
                        name,
                        exc,
                    )

            if pending:
                time.sleep(interval)

    if pending:
        raise RuntimeError(
            "Routers failed health checks: " + ", ".join(sorted(pending.keys()))
        )


def _get_router_for_path(path: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Determine which router should handle a given path.

    - Non-root prefixes (e.g., /mock1, /mock2) are matched first by longest prefix.
    - A router with prefix "/" or "" acts as the default router.
    - Returned tuple is (router_cfg, trimmed_path_for_router).
    """
    if not path.startswith("/"):
        path = "/" + path

    specific_routers: List[Dict[str, Any]] = [
        r
        for r in ROUTER_CONFIGS
        if r.get("prefix") not in ("", "/")
    ]
    specific_routers.sort(key=lambda r: len(r["prefix"]), reverse=True)

    for router in specific_routers:
        prefix = router["prefix"]
        if path == prefix or path.startswith(prefix + "/"):
            trimmed = path[len(prefix):] or "/"
            if not trimmed.startswith("/"):
                trimmed = "/" + trimmed
            return router, trimmed

    # Default router – see everything else, with original path preserved.
    default_router = next(
        (r for r in ROUTER_CONFIGS if r.get("prefix") in ("", "/")),
        None,
    )
    if default_router is not None:
        return default_router, path

    return None, path


app = FastAPI(title="Main Router")


@app.on_event("startup")
async def startup_event() -> None:
    # Shared HTTP client for proxying.
    app.state.http_client = httpx.AsyncClient()
    logger.info(
        "Main router started with %d configured child routers",
        len(ROUTER_CONFIGS),
    )


@app.on_event("shutdown")
async def shutdown_event() -> None:
    client: Optional[httpx.AsyncClient] = getattr(
        app.state, "http_client", None
    )
    if client:
        await client.aclose()


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check for the main router."""
    return {
        "status": "ok",
        "routers": [
            {
                "name": r["name"],
                "host": r.get("host", "127.0.0.1"),
                "port": r["port"],
                "prefix": r.get("prefix") or "",
            }
            for r in ROUTER_CONFIGS
        ],
    }


@app.get("/routers")
async def list_routers() -> Dict[str, Any]:
    """Return the loaded router configuration."""
    return {"main": MAIN_CONFIG, "routers": ROUTER_CONFIGS}


@app.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy_request(full_path: str, request: Request) -> Response:
    """
    Proxy any request to the appropriate router based on path prefix.

    Example:
    - /mock1/hello -> mock1 router (prefix=/mock1), path=/hello
    - /mock2/status -> mock2 router (prefix=/mock2), path=/status
    - /api/auth/start -> default router (prefix=/), path=/api/auth/start
    """
    path = "/" + full_path
    router_cfg, target_path = _get_router_for_path(path)

    if router_cfg is None:
        raise HTTPException(status_code=404, detail="No router configured for this path")

    client: httpx.AsyncClient = request.app.state.http_client

    url = httpx.URL(
        scheme="http",
        host=router_cfg.get("host", "127.0.0.1"),
        port=router_cfg["port"],
        path=target_path,
        query=request.url.query.encode("utf-8"),
    )

    headers = dict(request.headers)
    # Rewrite host header for upstream.
    headers["host"] = f"{router_cfg.get('host', '127.0.0.1')}:{router_cfg['port']}"

    body = await request.body()

    try:
        upstream_response = await client.request(
            request.method,
            url,
            content=body,
            headers=headers,
            timeout=None,
        )
    except httpx.RequestError as exc:
        logger.error(
            "Error proxying request to router %s: %s",
            router_cfg["name"],
            exc,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Upstream router {router_cfg['name']} unreachable",
        ) from exc

    excluded_headers = {
        "content-encoding",
        "transfer-encoding",
        "connection",
        "keep-alive",
    }
    response_headers = {
        k: v
        for k, v in upstream_response.headers.items()
        if k.lower() not in excluded_headers
    }

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=response_headers,
        media_type=upstream_response.headers.get("content-type"),
    )


if __name__ == "__main__":
    # When invoked as a script, start all routers and then the main router process.
    start_all_routers()
    try:
        try:
            wait_for_routers_ready()
        except RuntimeError as exc:
            logger.error("Router health checks failed: %s", exc)
            raise SystemExit(1)

        logger.info(
            "Starting main router on %s:%s with %s workers",
            MAIN_CONFIG["host"],
            MAIN_CONFIG["port"],
            MAIN_CONFIG.get("workers", 4),
        )
        uvicorn.run(
            "main:app",
            host=MAIN_CONFIG["host"],
            port=int(MAIN_CONFIG["port"]),
            workers=int(MAIN_CONFIG.get("workers", 4)),
            reload=bool(MAIN_CONFIG.get("reload", False)),
            log_level=str(MAIN_CONFIG.get("log_level", "info")),
        )
    finally:
        stop_all_routers()
