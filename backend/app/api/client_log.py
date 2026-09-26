import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

# Logs sent by the Fire TV app: they land in `docker logs animehub`.
logger = logging.getLogger("animehub.tv")

router = APIRouter()

_LEVELS = {"D": logging.INFO, "I": logging.INFO, "W": logging.WARNING, "E": logging.ERROR}


class ClientLogEntry(BaseModel):
    level: str = "I"
    tag: str = ""
    message: str = ""
    ts: str = ""


@router.post("/client-log", status_code=204)
async def client_log(entries: list[ClientLogEntry], request: Request):
    host = request.client.host if request.client else "?"
    for e in entries[:500]:
        logger.log(
            _LEVELS.get(e.level[:1].upper(), logging.INFO),
            "[%s %s] %s: %s", host, e.ts[:32], e.tag[:64], e.message[:50_000],
        )
