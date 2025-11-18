"""
Main router entrypoint.

This process:
- Reads router definitions from routers/config.json
- Starts each router as its own uvicorn process
- Runs a FastAPI gateway that proxies requests to routers based on path prefix
  for both HTTP and WebSocket connections.
"""
import asyncio
import importlib
import json
import logging
import logging.config
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
import uvicorn
import websockets
from websockets.exceptions import ConnectionClosed

BASE_DIR = Path(__file__).resolve().parent
ROUTERS_CONFIG_PATH = BASE_DIR / "routers" / "config.json"
LOGGING_CONFIG_PATH = BASE_DIR / "logging" / "log_config.json"

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


def _load_base_log_config() -> Dict[str, Any]:
    """Load the base logging configuration used as a template."""
    if not LOGGING_CONFIG_PATH.exists():
        raise RuntimeError(f"Logging config not found at {LOGGING_CONFIG_PATH}")

    with LOGGING_CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _build_log_config_for_name(base: Dict[str, Any], filename: str) -> Dict[str, Any]:
    """Return a copy of base log config with updated log filename."""
    config = json.loads(json.dumps(base))
    handlers = config.get("handlers", {})
    file_handler = handlers.get("file")
    if file_handler is not None:
        file_handler["filename"] = filename
    return config


def _ensure_router_log_config(router_name: str, base_log_config: Dict[str, Any]) -> Path:
    """
    Ensure a per-router log config file exists and return its path.

    The log file will be logging/<router_name>.log under BASE_DIR.
    """
    log_dir = BASE_DIR / "logging"
    log_dir.mkdir(parents=True, exist_ok=True)

    filename = str(log_dir / f"{router_name}.log")
    router_log_config = _build_log_config_for_name(base_log_config, filename)

    config_path = log_dir / f"log_config_{router_name}.json"
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(router_log_config, f)

    return config_path


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


def _start_router_process(router_cfg: Dict[str, Any], base_log_config: Dict[str, Any]) -> None:
    """Start a single router as a separate uvicorn process."""
    name = router_cfg["name"]
    if name in ROUTER_PROCESSES and ROUTER_PROCESSES[name].poll() is None:
        # Already running
        return

    host = router_cfg.get("host", "127.0.0.1")
    port = str(router_cfg["port"])
    router_path = router_cfg["router_path"]

    extra_args = router_cfg.get("uvicorn_args", [])

    # Per-router logging config file and log file.
    router_log_config_path = _ensure_router_log_config(
        name,
        base_log_config,
    )

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
        "--log-config",
        str(router_log_config_path),
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


def start_all_routers(base_log_config: Dict[str, Any]) -> None:
    """Start all configured routers."""
    for router_cfg in ROUTER_CONFIGS:
        _start_router_process(router_cfg, base_log_config)


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


@app.websocket("/{full_path:path}")
async def websocket_proxy(full_path: str, websocket: WebSocket) -> None:
    """
    Proxy WebSocket connections to the appropriate router based on path prefix.

    The same prefix logic as HTTP routing is applied:
    - /mock1/... -> mock1 router with trimmed path
    - /mock2/... -> mock2 router with trimmed path
    - everything else -> default router (e.g., auth-api)
    """
    path = "/" + full_path
    router_cfg, target_path = _get_router_for_path(path)

    await websocket.accept()

    if router_cfg is None:
        await websocket.close(code=1008)
        return

    host = router_cfg.get("host", "127.0.0.1")
    port = router_cfg["port"]
    query = websocket.url.query

    upstream_url = f"ws://{host}:{port}{target_path}"
    if query:
        upstream_url = f"{upstream_url}?{query}"

    # Forward headers such as subprotocols to upstream.
    extra_headers = dict(websocket.headers)
    extra_headers["host"] = f"{host}:{port}"

    logger.info(
        "Proxying WebSocket %s to %s",
        path,
        upstream_url,
    )

    try:
        async with websockets.connect(
            upstream_url,
            extra_headers=extra_headers,
        ) as upstream:

            async def client_to_upstream() -> None:
                try:
                    while True:
                        message = await websocket.receive()
                        message_type = message.get("type")

                        if message_type == "websocket.disconnect":
                            await upstream.close()
                            break

                        text_data = message.get("text")
                        if text_data is not None:
                            await upstream.send(text_data)
                            continue

                        bytes_data = message.get("bytes")
                        if bytes_data is not None:
                            await upstream.send(bytes_data)
                except WebSocketDisconnect:
                    await upstream.close()

            async def upstream_to_client() -> None:
                try:
                    while True:
                        data = await upstream.recv()
                        if isinstance(data, str):
                            await websocket.send_text(data)
                        else:
                            await websocket.send_bytes(data)
                except ConnectionClosed:
                    await websocket.close()

            sender = asyncio.create_task(client_to_upstream())
            receiver = asyncio.create_task(upstream_to_client())

            done, pending = await asyncio.wait(
                {sender, receiver},
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

    except Exception as exc:
        logger.error(
            "Error proxying WebSocket for %s to router %s: %s",
            path,
            router_cfg["name"] if router_cfg else "unknown",
            exc,
        )
        with contextlib.suppress(Exception):
            await websocket.close(code=1011)


if __name__ == "__main__":
    # When invoked as a script, start all routers and then the main router process.
    # Configure logging for the main process.
    base_log_config = _load_base_log_config()
    main_log_dir = BASE_DIR / "logging"
    main_log_dir.mkdir(parents=True, exist_ok=True)
    main_log_filename = str(main_log_dir / "main.log")
    main_log_config = _build_log_config_for_name(base_log_config, main_log_filename)
    logging.config.dictConfig(main_log_config)

    start_all_routers(base_log_config)
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
            log_config=main_log_config,
        )
    finally:
        stop_all_routers()
