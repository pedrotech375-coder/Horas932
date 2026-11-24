#!/usr/bin/env python3
"""Calcula horas restantes con datos MySQL recibidos por la API.

La API es la fuente oficial. En cada ejecución online se actualiza localmente
materias_932.db; en modo offline se usa la última respuesta cacheada o, si aún
no existe, el respaldo inicial 2026-2. No se requiere instalar paquetes.
"""
import json
import math
import os
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DB = Path(os.getenv("HORAS932_SQLITE_PATH", str(Path(__file__).with_name("materias_932.db"))))
API_BASE_URL = os.getenv("HORAS932_API_BASE_URL", "https://horas932-3rxpt5kn.manus.space").rstrip("/")
GRUPO = "932"
PERIODO_SOLICITADO = os.getenv("HORAS932_PERIODO", "").strip()
DIAS = {0: "lunes", 1: "martes", 2: "miercoles", 3: "jueves", 4: "viernes"}
MOTIVOS_SUSPENSION = {
    1: "Clima",
    2: "Emergencia personal",
    3: "Seguridad",
    4: "Fenómeno natural",
}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
REQUIRED_MATERIA_COLUMNS = {
    "materia", "lunes_horas", "martes_horas", "miercoles_horas",
    "jueves_horas", "viernes_horas", "horas_totales_semana",
}


def desde_iso(valor):
    return date.fromisoformat(str(valor)[:10])


def _horas_no_negativas(valor, campo):
    try:
        numero = float(valor or 0)
    except (TypeError, ValueError) as error:
        raise ValueError(f"La API devolvió un valor inválido para {campo}.") from error
    if not math.isfinite(numero) or numero < 0:
        raise ValueError(f"La API devolvió un valor inválido para {campo}.")
    return numero


def normalizar_payload(datos, fuente):
    """Valida la estructura compartida y la convierte al formato del cálculo."""
    requeridos = (
        "periodo", "grupo", "fecha_fin_regular", "fecha_fin_calculo",
        "fechas_adicionales", "exclusiones", "materias",
    )
    if not isinstance(datos, dict) or not all(clave in datos for clave in requeridos):
        raise ValueError("La respuesta de la API no contiene todos los datos del periodo.")

    periodo = str(datos["periodo"])
    try:
        grupo = int(datos["grupo"])
    except (TypeError, ValueError) as error:
        raise ValueError("La API devolvió un grupo inválido.") from error
    if not re.fullmatch(r"\d{4}-\d{1,2}", periodo):
        raise ValueError("La API devolvió un periodo inválido.")
    if not GRUPO.isdigit() or grupo != int(GRUPO):
        raise ValueError("La respuesta de la API no corresponde al grupo solicitado.")
    if PERIODO_SOLICITADO and periodo != PERIODO_SOLICITADO:
        raise ValueError("La respuesta de la API no corresponde al periodo solicitado.")

    fecha_fin_regular = desde_iso(datos["fecha_fin_regular"])
    fecha_fin_calculo = desde_iso(datos["fecha_fin_calculo"])
    if fecha_fin_calculo < fecha_fin_regular:
        raise ValueError("La API devolvió un rango de cálculo inválido.")

    fechas_adicionales = datos["fechas_adicionales"]
    exclusiones_api = datos["exclusiones"]
    filas_api = datos["materias"]
    if not isinstance(fechas_adicionales, list) or not isinstance(exclusiones_api, list):
        raise ValueError("La API devolvió un calendario inválido.")
    if not isinstance(filas_api, list) or not filas_api:
        raise ValueError("La API no devolvió materias para este periodo.")

    materias = []
    for fila in filas_api:
        if not isinstance(fila, dict) or not str(fila.get("nombre", "")).strip():
            raise ValueError("La API devolvió una materia inválida.")
        horas_origen = fila.get("horas") or {}
        if not isinstance(horas_origen, dict):
            raise ValueError("La API devolvió horas semanales inválidas.")
        horas = {dia: _horas_no_negativas(horas_origen.get(dia, 0), dia) for dia in DIAS.values()}
        total = _horas_no_negativas(fila.get("horas_totales_semana", sum(horas.values())), "total semanal")
        if abs(total - sum(horas.values())) > 0.01:
            raise ValueError(f"El total semanal no coincide con el horario de {fila['nombre']}.")
        materias.append({"nombre": str(fila["nombre"]).strip(), "horas": horas, "total": total})

    exclusiones = []
    for evento in exclusiones_api:
        claves_evento = {"tipo", "fecha_inicio", "fecha_fin", "descripcion"}
        if not isinstance(evento, dict) or not claves_evento.issubset(evento):
            raise ValueError("La API devolvió una exclusión inválida.")
        inicio = desde_iso(evento["fecha_inicio"])
        fin = desde_iso(evento["fecha_fin"])
        if fin < inicio:
            raise ValueError("La API devolvió un rango de fechas inválido.")
        exclusiones.append((inicio, fin))

    return {
        "periodo": periodo,
        "grupo": grupo,
        "fecha_fin_regular": fecha_fin_regular,
        "fecha_fin_calculo": fecha_fin_calculo,
        "fechas_adicionales": {desde_iso(fecha) for fecha in fechas_adicionales},
        "exclusiones": exclusiones,
        "materias": materias,
        "fuente": fuente,
    }


def cargar_api():
    """Obtiene el periodo activo o el periodo explícito desde el API compartido."""
    parametros = {"grupo": GRUPO}
    if PERIODO_SOLICITADO:
        parametros["periodo"] = PERIODO_SOLICITADO
    url = f"{API_BASE_URL}/api/v1/horario?{urlencode(parametros)}"
    solicitud = Request(url, headers={"Accept": "application/json", "User-Agent": "Horas932-Python/2.0"})
    with urlopen(solicitud, timeout=8) as respuesta:
        if respuesta.status != 200:
            raise RuntimeError(f"La API respondió con estado {respuesta.status}.")
        datos = json.loads(respuesta.read().decode("utf-8"))
    return normalizar_payload(datos, "API compartida"), datos


def sincronizar_sqlite(datos):
    """Refresca SQLite en una transacción; no realiza escrituras en MySQL."""
    configuracion = normalizar_payload(datos, "API compartida")
    if configuracion["grupo"] != 932:
        raise ValueError("La base local materias_932.db está destinada al grupo 932.")

    DB.parent.mkdir(parents=True, exist_ok=True)
    sincronizada = datetime.now(timezone.utc).isoformat(timespec="seconds")
    calendario = []
    for fecha in datos["fechas_adicionales"]:
        calendario.append((
            configuracion["grupo"], configuracion["periodo"], "adicional",
            str(fecha)[:10], str(fecha)[:10], "Fecha adicional de clase",
        ))
    for evento in datos["exclusiones"]:
        calendario.append((
            configuracion["grupo"], configuracion["periodo"],
            str(evento.get("tipo", "exclusion")), str(evento["fecha_inicio"])[:10],
            str(evento["fecha_fin"])[:10], str(evento.get("descripcion", "")),
        ))

    conexion = sqlite3.connect(DB, timeout=10)
    try:
        conexion.execute("PRAGMA busy_timeout = 10000")
        conexion.execute("PRAGMA foreign_keys = ON")
        conexion.execute("BEGIN IMMEDIATE")
        conexion.execute(
            """CREATE TABLE IF NOT EXISTS materias_932 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                materia TEXT NOT NULL UNIQUE,
                lunes_horas REAL NOT NULL DEFAULT 0,
                martes_horas REAL NOT NULL DEFAULT 0,
                miercoles_horas REAL NOT NULL DEFAULT 0,
                jueves_horas REAL NOT NULL DEFAULT 0,
                viernes_horas REAL NOT NULL DEFAULT 0,
                horas_totales_semana REAL NOT NULL
            )"""
        )
        conexion.execute(
            """CREATE TABLE IF NOT EXISTS calendario_932 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                grupo INTEGER NOT NULL,
                periodo TEXT NOT NULL,
                tipo TEXT NOT NULL,
                fecha_inicio TEXT NOT NULL,
                fecha_fin TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                UNIQUE (grupo, periodo, tipo, fecha_inicio, fecha_fin, descripcion)
            )"""
        )
        conexion.execute(
            """CREATE TABLE IF NOT EXISTS horario_cache (
                grupo INTEGER NOT NULL,
                periodo TEXT NOT NULL,
                ultima_sincronizacion TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (grupo, periodo)
            )"""
        )

        columnas = {fila[1] for fila in conexion.execute("PRAGMA table_info(materias_932)")}
        if not REQUIRED_MATERIA_COLUMNS.issubset(columnas):
            raise sqlite3.DatabaseError("La tabla local materias_932 tiene un esquema incompatible.")

        conexion.execute("DELETE FROM materias_932")
        conexion.executemany(
            """INSERT INTO materias_932 (
                materia, lunes_horas, martes_horas, miercoles_horas,
                jueves_horas, viernes_horas, horas_totales_semana
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    materia["nombre"], materia["horas"]["lunes"], materia["horas"]["martes"],
                    materia["horas"]["miercoles"], materia["horas"]["jueves"],
                    materia["horas"]["viernes"], materia["total"],
                )
                for materia in configuracion["materias"]
            ],
        )
        conexion.execute(
            "DELETE FROM calendario_932 WHERE grupo = ? AND periodo = ?",
            (configuracion["grupo"], configuracion["periodo"]),
        )
        conexion.executemany(
            """INSERT INTO calendario_932
               (grupo, periodo, tipo, fecha_inicio, fecha_fin, descripcion)
               VALUES (?, ?, ?, ?, ?, ?)""",
            calendario,
        )
        conexion.execute(
            """INSERT OR REPLACE INTO horario_cache
               (grupo, periodo, ultima_sincronizacion, payload_json)
               VALUES (?, ?, ?, ?)""",
            (
                configuracion["grupo"], configuracion["periodo"], sincronizada,
                json.dumps(datos, ensure_ascii=False, separators=(",", ":")),
            ),
        )
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()
    return sincronizada


def _leer_cache_local():
    if not DB.exists():
        return None
    try:
        with sqlite3.connect(DB, timeout=5) as conexion:
            existe = conexion.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='horario_cache'"
            ).fetchone()
            if not existe:
                return None
            if PERIODO_SOLICITADO:
                fila = conexion.execute(
                    """SELECT payload_json, ultima_sincronizacion FROM horario_cache
                       WHERE grupo = ? AND periodo = ? LIMIT 1""",
                    (int(GRUPO), PERIODO_SOLICITADO),
                ).fetchone()
            else:
                fila = conexion.execute(
                    """SELECT payload_json, ultima_sincronizacion FROM horario_cache
                       WHERE grupo = ? ORDER BY ultima_sincronizacion DESC LIMIT 1""",
                    (int(GRUPO),),
                ).fetchone()
    except (sqlite3.Error, ValueError):
        return None
    if not fila:
        return None
    payload, sincronizada = fila
    fuente = f"caché SQLite sincronizada el {sincronizada} (puede estar desactualizada)"
    return normalizar_payload(json.loads(payload), fuente)


def cargar_sqlite_local():
    """Carga el último snapshot local o el respaldo inicial 2026-2."""
    try:
        cache = _leer_cache_local()
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        cache = None
    if cache:
        return cache

    if not GRUPO.isdigit() or int(GRUPO) != 932:
        raise RuntimeError("No hay una copia SQLite de ese grupo; no se usó un horario distinto.")
    if PERIODO_SOLICITADO and PERIODO_SOLICITADO != "2026-2":
        raise RuntimeError(
            f"No hay una copia local sincronizada para el periodo {PERIODO_SOLICITADO}; no se usó otro periodo."
        )
    if not DB.exists():
        raise FileNotFoundError(f"No se encontró la base de respaldo: {DB.name}")

    with sqlite3.connect(DB) as conexion:
        filas = conexion.execute(
            """SELECT materia, lunes_horas, martes_horas, miercoles_horas,
                      jueves_horas, viernes_horas, horas_totales_semana
               FROM materias_932 ORDER BY materia"""
        ).fetchall()
    if not filas:
        raise RuntimeError("La tabla materias_932 no contiene materias.")

    materias = []
    for fila in filas:
        materias.append({
            "nombre": fila[0],
            "horas": dict(zip(DIAS.values(), map(float, fila[1:6]))),
            "total": float(fila[6]),
        })
    exclusiones = [
        (date(2026, 11, 2), date(2026, 11, 2)),
        (date(2026, 11, 16), date(2026, 11, 16)),
        (date(2026, 11, 30), date(2026, 12, 8)),
        (date(2026, 12, 14), date(2026, 12, 17)),
        (date(2026, 12, 18), date(2026, 12, 18)),
    ]
    return {
        "periodo": "2026-2",
        "grupo": 932,
        "fecha_fin_regular": date(2026, 11, 30),
        "fecha_fin_calculo": date(2026, 12, 11),
        "fechas_adicionales": {date(2026, 12, 9), date(2026, 12, 10), date(2026, 12, 11)},
        "exclusiones": exclusiones,
        "materias": materias,
        "fuente": "respaldo SQLite inicial 2026-2 (puede estar desactualizado)",
    }


def obtener_configuracion():
    try:
        configuracion, payload = cargar_api()
    except (
        HTTPError, URLError, TimeoutError, OSError, ValueError,
        TypeError, KeyError, RuntimeError,
    ) as error:
        print(f"No se pudo consultar la API compartida ({type(error).__name__}).")
        print("El respaldo SQLite local puede estar desactualizado respecto al periodo activo.")
        while True:
            respuesta = input("¿Deseas continuar sin conexión con el respaldo local? (s/n): ").strip().lower()
            if respuesta in ("s", "si", "sí"):
                try:
                    return cargar_sqlite_local()
                except (FileNotFoundError, RuntimeError, sqlite3.Error, ValueError) as error_local:
                    raise SystemExit(f"No se pudo usar el respaldo local ({type(error_local).__name__}).") from error_local
            if respuesta in ("n", "no"):
                raise SystemExit("Cálculo cancelado; no se usó una copia local.")
            print("Responde s para continuar sin conexión o n para cancelar.\n")

    try:
        sincronizada = sincronizar_sqlite(payload)
        configuracion["fuente"] = f"API MySQL compartida; SQLite sincronizada el {sincronizada}"
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f"No se actualizó la caché SQLite ({type(error).__name__}); continuaré con los datos vigentes del API.")
        configuracion["fuente"] = "API MySQL compartida (caché local no actualizada)"
    return configuracion


def seleccionar_materia(materias):
    print("\nSelecciona la materia escribiendo su número:")
    for numero, materia in enumerate(materias, start=1):
        print(f"{numero}. {materia['nombre']} ({materia['total']:g} h por semana)")
    while True:
        respuesta = input(f"Número de materia (1-{len(materias)}): ").strip()
        try:
            numero = int(respuesta)
        except ValueError:
            print("Opción no válida. Escribe uno de los números de la lista.\n")
            continue
        if 1 <= numero <= len(materias):
            return materias[numero - 1]
        print(f"Opción no válida. Elige un número del 1 al {len(materias)}.\n")


def seleccionar_motivo():
    while True:
        print("Motivo de la suspensión:")
        for numero, motivo in MOTIVOS_SUSPENSION.items():
            print(f"{numero}. {motivo}")
        print("5. Otro (escribir)")
        respuesta = input("Selecciona el número del motivo: ").strip()
        try:
            opcion = int(respuesta)
        except ValueError:
            print("Opción no válida. Escribe un número del 1 al 5.\n")
            continue
        if opcion in MOTIVOS_SUSPENSION:
            return MOTIVOS_SUSPENSION[opcion]
        if opcion == 5:
            while True:
                motivo = input("Escribe el otro motivo: ").strip()
                if motivo:
                    return motivo
                print("El motivo no puede quedar vacío.\n")
        print("Opción no válida. Elige un número del 1 al 5.\n")


def leer_fecha(texto, anio):
    try:
        fecha = datetime.strptime(texto, "%d/%m/%Y").date()
    except ValueError as error:
        raise ValueError("Usa el formato dd/mm/aaaa.") from error
    if fecha.year != anio:
        raise ValueError(f"La fecha debe pertenecer al año {anio}.")
    return fecha


def fecha_legible(fecha):
    return f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"


def rango_adicional_legible(fechas):
    ordenadas = sorted(fechas)
    if not ordenadas:
        return "sin fechas adicionales"
    if len(ordenadas) == 1:
        return fecha_legible(ordenadas[0])
    primera, ultima = ordenadas[0], ordenadas[-1]
    if primera.month == ultima.month and primera.year == ultima.year:
        return f"del {primera.day} al {ultima.day} de {MESES[ultima.month - 1]}"
    return f"del {fecha_legible(primera)} al {fecha_legible(ultima)}"


def dia_excluido(fecha, rangos, suspensiones):
    return fecha in suspensiones or any(inicio <= fecha <= fin for inicio, fin in rangos)


def calcular(materia, fecha_hoy, configuracion, suspensiones_extra):
    """Devuelve las horas regulares y adicionales que quedan por impartir."""
    dia = fecha_hoy + timedelta(days=1)
    regular = 0.0
    adicional = 0.0
    while dia <= configuracion["fecha_fin_calculo"]:
        if dia.weekday() < 5 and not dia_excluido(dia, configuracion["exclusiones"], suspensiones_extra):
            horas = materia["horas"].get(DIAS[dia.weekday()], 0)
            if dia <= configuracion["fecha_fin_regular"]:
                regular += horas
            elif dia in configuracion["fechas_adicionales"]:
                adicional += horas
        dia += timedelta(days=1)
    return regular, adicional


def main():
    configuracion = obtener_configuracion()
    anio = int(configuracion["periodo"].split("-")[0])
    print(f"\nFuente de horarios: {configuracion['fuente']}.")
    print(f"Grupo {configuracion['grupo']} · periodo {configuracion['periodo']}\n")
    materia = seleccionar_materia(configuracion["materias"])

    while True:
        texto_fecha = input("¿Qué fecha es hoy? (dd/mm/aaaa): ").strip()
        try:
            hoy = leer_fecha(texto_fecha, anio)
            break
        except ValueError as error:
            print(f"Fecha no válida. {error}\n")

    suspensiones = {}
    while True:
        respuesta = input("¿Hubo suspensión emergente confirmada? (s/n): ").strip().lower()
        if respuesta in ("s", "si", "sí"):
            print("Ingresa cada fecha confirmada como dd/mm/aaaa; deja vacío para terminar.")
            while True:
                texto = input("Fecha suspendida: ").strip()
                if not texto:
                    break
                try:
                    fecha = leer_fecha(texto, anio)
                except ValueError as error:
                    print(f"Fecha no válida. {error}\n")
                    continue
                if fecha in suspensiones:
                    print("Esa fecha ya fue registrada.\n")
                    continue
                motivo = seleccionar_motivo()
                suspensiones[fecha] = motivo
                print(f"Registrada: {fecha:%d/%m/%Y} — {motivo}\n")
            break
        if respuesta in ("n", "no"):
            break
        print("Responde s o n.\n")

    regular, adicional = calcular(materia, hoy, configuracion, set(suspensiones))
    if suspensiones:
        print("\nSuspensiones confirmadas:")
        for fecha, motivo in sorted(suspensiones.items()):
            print(f" - {fecha:%d/%m/%Y}: {motivo}")
    print(f"\nHoras restantes hasta el {configuracion['fecha_fin_regular']:%d/%m/%Y}: {regular:g}")
    print(f"Horas adicionales ({rango_adicional_legible(configuracion['fechas_adicionales'])}): {adicional:g}")
    print(f"Total contando las fechas adicionales: {regular + adicional:g} horas")


if __name__ == "__main__":
    main()
