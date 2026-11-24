"""Backend FastAPI de Horas 932; MySQL solo se consulta desde el servidor."""
from __future__ import annotations

import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import pymysql
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from db.migrate import run_migrations
from db.mysql import (
    DatabaseConfigurationError,
    MultipleActivePeriods,
    ScheduleNotFound,
    fetch_schedule,
    ping_database,
)

logger = logging.getLogger("horas932")
STATIC_DIR = Path(__file__).with_name("public")
VALID_GROUP = re.compile(r"^[0-9]{1,5}$")
VALID_PERIOD = re.compile(r"^[0-9]{4}-[0-9]{1,2}$")
API_METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    run_migrations()
    yield


app = FastAPI(
    title="Horas 932 API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)


def _json(status_code: int, body: dict) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=body,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


def _method_guard(request: Request) -> JSONResponse | None:
    if request.method not in ("GET", "HEAD"):
        return _json(405, {"error": "La API solo admite solicitudes de lectura."})
    return None


@app.api_route("/api/health", methods=API_METHODS, include_in_schema=False)
def health(request: Request):
    rejected = _method_guard(request)
    if rejected:
        return rejected
    try:
        ping_database()
    except (pymysql.MySQLError, DatabaseConfigurationError, OSError) as exc:
        logger.warning("Error en health check MySQL (%s).", type(exc).__name__)
        return _json(503, {"status": "error", "database": "unavailable"})
    return _json(200, {"status": "ok", "database": "ok"})


@app.api_route("/api/v1/horario", methods=API_METHODS, include_in_schema=False)
def schedule(request: Request):
    rejected = _method_guard(request)
    if rejected:
        return rejected

    grupo_texto = request.query_params.get("grupo", "932")
    periodo_solicitado = request.query_params.get("periodo")
    if not VALID_GROUP.fullmatch(grupo_texto) or (
        periodo_solicitado is not None and not VALID_PERIOD.fullmatch(periodo_solicitado)
    ):
        return _json(
            400,
            {"error": "Parámetros inválidos. Usa grupo numérico y un periodo como 2026-2."},
        )

    try:
        datos = fetch_schedule(int(grupo_texto), periodo_solicitado)
    except ScheduleNotFound as exc:
        return _json(404, {"error": str(exc)})
    except MultipleActivePeriods as exc:
        return _json(409, {"error": str(exc)})
    except (pymysql.MySQLError, DatabaseConfigurationError, OSError) as exc:
        logger.warning("Error al consultar horario MySQL (%s).", type(exc).__name__)
        return _json(
            503,
            {"error": "No se pudo consultar el horario. Intenta de nuevo más tarde."},
        )
    return _json(200, datos)


@app.api_route("/api/{ruta:path}", methods=API_METHODS, include_in_schema=False)
def unknown_api(request: Request, ruta: str):
    rejected = _method_guard(request)
    if rejected:
        return rejected
    return _json(404, {"error": "Ruta de API no encontrada."})


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


# En producción, Webdev separa el sitio estático del contenedor. Este montaje
# conserva el mismo frontend durante Preview y ejecución local.
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
