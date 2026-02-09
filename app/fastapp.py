# fastapp.py

import atexit
import logging
import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, Request, WebSocketException, status
from fastapi.concurrency import asynccontextmanager
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.websockets import WebSocketState
from starlette.middleware.base import BaseHTTPMiddleware
from app.graph import runGraph
from app.utility import SocketRequest

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s[%(name)s]: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)

logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = [
    "http://localhost:4200",
    "http://localhost",
    "https://localhost:4200",
    "https://localhost",
    "http://127.0.0.1",
    "https://127.0.0.1",
]

SERVER_INIT = False


# FastApi lifespan, executes when fastapi starts and stops
@asynccontextmanager
async def lifeSpan(app: FastAPI):
    global SERVER_INIT
    if not SERVER_INIT:
        logger.info("Initializing server completed.")
        SERVER_INIT = True
    else:
        logger.info("Server is ready.")
    yield
    try:
        logger.info("Server is shutting down...")
    except Exception as err:
        logger.error("Server level exception. %s", err)


# Register backup cleanup on exiting program
@atexit.register
def cleanUp():
    logger.info("Program cleaned, exit...")


class ValidateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        requestId = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.requestId = requestId

        response = await call_next(request)
        response.headers["X-Request-ID"] = requestId
        return response


app = FastAPI(
    title="Auto Support Pilot",
    description="Smart hybrid langchain langgraph agent.",
    lifespan=lifeSpan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
)
app.add_middleware(ValidateMiddleware)


@app.get("/")
async def getHome(request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content={"status": "success", "content": "Connection ok."},
    )


@app.websocket("/ws")
async def aiWebSocket(ws: WebSocket):
    """Secure Websocket, "Cross-Site WebSocket Hijacking" (CSWH)"""
    origin = ws.headers.get("origin")
    if origin not in ALLOWED_ORIGINS:
        await ws.close(code=status.WS_1014_BAD_GATEWAY, reason="CORS error")
        return

    requestId = ws.headers.get("X-Request-ID") or str(uuid.uuid4())

    await ws.accept()
    logger.info("Connection established %s", ws.client)
    try:
        while True:
            data = await ws.receive_json()
            if not data:
                continue

            requestData = SocketRequest.model_validate(data, extra="ignore")
            if not requestData.requestId:
                requestData.requestId = requestId

            await runGraph(requestData, ws)

    except WebSocketException as err:
        logger.exception(
            "Socket level exception. %s", err, extra={"method": "aiWebSocket"}
        )
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.send_json({"error": True, "message": "Internal Server Error."})
    except Exception as err:
        logger.exception(
            "Server level exception. %s", err, extra={"method": "aiWebSocket"}
        )
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.send_json({"error": True, "message": "Internal Server Error."})
