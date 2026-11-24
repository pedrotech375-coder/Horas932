"""Conexión y consultas de solo lectura a MySQL gestionado."""
from __future__ import annotations

import json
import os
import ssl as ssl_module
from urllib.parse import parse_qs, unquote, urlsplit

import pymysql
from pymysql.cursors import DictCursor


class DatabaseConfigurationError(RuntimeError):
    """La conexión MySQL no está configurada o el DSN no es válido."""


class ScheduleNotFound(LookupError):
    """No existe horario para el grupo/periodo solicitado."""


class MultipleActivePeriods(RuntimeError):
    """Hay más de un periodo activo para un grupo."""


def _ssl_options(query: dict[str, list[str]]) -> dict | None:
    values = query.get("ssl")
    if not values:
        return None

    raw = values[-1]
    try:
        config = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise DatabaseConfigurationError("La opción TLS de DATABASE_URL no es JSON válido.") from exc
    if not isinstance(config, dict):
        raise DatabaseConfigurationError("La opción TLS de DATABASE_URL debe ser un objeto.")

    options: dict[str, object] = {}
    reject_unauthorized = config.get("rejectUnauthorized")
    if reject_unauthorized is not None:
        if not isinstance(reject_unauthorized, bool):
            raise DatabaseConfigurationError("rejectUnauthorized debe ser booleano.")
        verify = reject_unauthorized
        options["check_hostname"] = verify
        options["verify_mode"] = ssl_module.CERT_REQUIRED if verify else ssl_module.CERT_NONE

    for key in ("ca", "capath", "cadata", "cert", "key", "cipher"):
        value = config.get(key)
        if value is None:
            continue
        if key == "ca" and isinstance(value, str) and "-----BEGIN CERTIFICATE-----" in value:
            options["cadata"] = value
        else:
            options[key] = value

    # La presencia de un objeto SSL, aunque no incluya ajustes adicionales,
    # solicita TLS al driver. La configuración recibida actualmente exige
    # validación del certificado y del nombre del host.
    return options


def connect_mysql():
    """Abre una conexión PyMySQL con los parámetros seguros del DSN de runtime."""
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        raise DatabaseConfigurationError("DATABASE_URL no está configurada en el servidor.")

    try:
        parsed = urlsplit(dsn)
        port = parsed.port or 3306
    except ValueError as exc:
        raise DatabaseConfigurationError("DATABASE_URL no es un DSN MySQL válido.") from exc

    if parsed.scheme not in ("mysql", "mysql+pymysql") or not parsed.hostname or not parsed.path.strip("/"):
        raise DatabaseConfigurationError("DATABASE_URL no es un DSN MySQL válido.")

    query = parse_qs(parsed.query, keep_blank_values=True)
    kwargs = {
        "host": parsed.hostname,
        "port": port,
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "database": unquote(parsed.path.lstrip("/")),
        "charset": query.get("charset", ["utf8mb4"])[-1],
        "cursorclass": DictCursor,
        "autocommit": True,
        "connect_timeout": 10,
        "read_timeout": 20,
        "write_timeout": 20,
    }
    ssl_config = _ssl_options(query)
    if ssl_config is not None:
        kwargs["ssl"] = ssl_config

    return pymysql.connect(**kwargs)


def ping_database() -> None:
    connection = connect_mysql()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    finally:
        connection.close()


def fetch_schedule(grupo: int, periodo_solicitado: str | None = None) -> dict:
    """Consulta periodo, materias y calendario con consultas parametrizadas."""
    connection = connect_mysql()
    try:
        with connection.cursor() as cursor:
            if periodo_solicitado:
                cursor.execute(
                    """SELECT periodo, grupo,
                              DATE_FORMAT(fecha_fin_regular, '%%Y-%%m-%%d') AS fecha_fin_regular,
                              DATE_FORMAT(fecha_fin_calculo, '%%Y-%%m-%%d') AS fecha_fin_calculo
                       FROM periodos_932
                       WHERE grupo = %s AND periodo = %s
                       LIMIT 2""",
                    (grupo, periodo_solicitado),
                )
            else:
                cursor.execute(
                    """SELECT periodo, grupo,
                              DATE_FORMAT(fecha_fin_regular, '%%Y-%%m-%%d') AS fecha_fin_regular,
                              DATE_FORMAT(fecha_fin_calculo, '%%Y-%%m-%%d') AS fecha_fin_calculo
                       FROM periodos_932
                       WHERE grupo = %s AND activo = 1
                       ORDER BY periodo DESC
                       LIMIT 2""",
                    (grupo,),
                )
            periodos = cursor.fetchall()

            if not periodos:
                raise ScheduleNotFound("No hay un periodo disponible para ese grupo.")
            if not periodo_solicitado and len(periodos) > 1:
                raise MultipleActivePeriods("Hay más de un periodo activo; contacta al administrador de datos.")

            periodo = periodos[0]
            periodo_id = periodo["periodo"]
            cursor.execute(
                """SELECT id, materia, lunes_horas, martes_horas, miercoles_horas,
                          jueves_horas, viernes_horas, horas_totales_semana
                   FROM materias_932
                   WHERE grupo = %s AND periodo = %s
                   ORDER BY materia""",
                (grupo, periodo_id),
            )
            filas_materias = cursor.fetchall()
            cursor.execute(
                """SELECT tipo,
                          DATE_FORMAT(fecha_inicio, '%%Y-%%m-%%d') AS fecha_inicio,
                          DATE_FORMAT(fecha_fin, '%%Y-%%m-%%d') AS fecha_fin,
                          descripcion
                   FROM calendario_932
                   WHERE grupo = %s AND periodo = %s
                   ORDER BY fecha_inicio, id""",
                (grupo, periodo_id),
            )
            filas_calendario = cursor.fetchall()

        if not filas_materias:
            raise ScheduleNotFound("El periodo existe, pero aún no tiene materias registradas.")

        calendario = [
            {
                "tipo": fila["tipo"],
                "fecha_inicio": str(fila["fecha_inicio"]),
                "fecha_fin": str(fila["fecha_fin"]),
                "descripcion": fila["descripcion"],
            }
            for fila in filas_calendario
        ]
        return {
            "periodo": str(periodo["periodo"]),
            "grupo": int(periodo["grupo"]),
            "fecha_fin_regular": str(periodo["fecha_fin_regular"]),
            "fecha_fin_calculo": str(periodo["fecha_fin_calculo"]),
            "fechas_adicionales": [
                evento["fecha_inicio"] for evento in calendario if evento["tipo"] == "adicional"
            ],
            "exclusiones": [evento for evento in calendario if evento["tipo"] != "adicional"],
            "materias": [
                {
                    "id": int(fila["id"]),
                    "nombre": fila["materia"],
                    "horas": {
                        "lunes": float(fila["lunes_horas"]),
                        "martes": float(fila["martes_horas"]),
                        "miercoles": float(fila["miercoles_horas"]),
                        "jueves": float(fila["jueves_horas"]),
                        "viernes": float(fila["viernes_horas"]),
                    },
                    "horas_totales_semana": float(fila["horas_totales_semana"]),
                }
                for fila in filas_materias
            ],
        }
    finally:
        connection.close()
