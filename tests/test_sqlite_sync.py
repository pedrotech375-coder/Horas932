import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools import calcular_horas_932 as client


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_DATABASE = PROJECT_ROOT / "tools" / "materias_932.db"
PAYLOAD = {
    "periodo": "2026-2",
    "grupo": 932,
    "fecha_fin_regular": "2026-11-30",
    "fecha_fin_calculo": "2026-12-11",
    "fechas_adicionales": ["2026-12-09", "2026-12-10", "2026-12-11"],
    "exclusiones": [
        {"tipo": "suspension_laboral", "fecha_inicio": "2026-11-02", "fecha_fin": "2026-11-02", "descripcion": "Suspensión laboral"},
        {"tipo": "suspension_laboral", "fecha_inicio": "2026-11-16", "fecha_fin": "2026-11-16", "descripcion": "Suspensión laboral"},
        {"tipo": "examen_ordinario", "fecha_inicio": "2026-11-30", "fecha_fin": "2026-12-08", "descripcion": "Exámenes ordinarios"},
        {"tipo": "examen_extraordinario", "fecha_inicio": "2026-12-14", "fecha_fin": "2026-12-17", "descripcion": "Exámenes extraordinarios"},
        {"tipo": "suspension_laboral", "fecha_inicio": "2026-12-18", "fecha_fin": "2026-12-18", "descripcion": "Suspensión laboral"},
    ],
    "materias": [
        {"id": 1, "nombre": "Análisis de Procesos y Datos de Negocios", "horas": {"lunes": 0, "martes": 0, "miercoles": 0, "jueves": 0, "viernes": 2}, "horas_totales_semana": 2},
        {"id": 2, "nombre": "Estadística Inferencial", "horas": {"lunes": 1, "martes": 0, "miercoles": 1, "jueves": 1, "viernes": 0}, "horas_totales_semana": 3},
        {"id": 3, "nombre": "Fundamentos de Metodología de la Investigación", "horas": {"lunes": 0, "martes": 0, "miercoles": 0, "jueves": 2, "viernes": 0}, "horas_totales_semana": 2},
        {"id": 4, "nombre": "Fundamentos de Redes", "horas": {"lunes": 0, "martes": 0, "miercoles": 2, "jueves": 0, "viernes": 2}, "horas_totales_semana": 4},
        {"id": 5, "nombre": "Lógica para los negocios", "horas": {"lunes": 2, "martes": 0, "miercoles": 1, "jueves": 0, "viernes": 0}, "horas_totales_semana": 3},
        {"id": 6, "nombre": "Programación", "horas": {"lunes": 2, "martes": 2, "miercoles": 0, "jueves": 2, "viernes": 0}, "horas_totales_semana": 6},
        {"id": 7, "nombre": "Sistemas de Información para Inteligencia de Negocios", "horas": {"lunes": 0, "martes": 2, "miercoles": 0, "jueves": 0, "viernes": 0}, "horas_totales_semana": 2},
    ],
}


class SqliteSyncTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Path(self.tempdir.name) / "materias_932.db"
        shutil.copy2(BASE_DATABASE, self.database)
        self.old_db = client.DB
        self.old_group = client.GRUPO
        self.old_period = client.PERIODO_SOLICITADO
        client.DB = self.database
        client.GRUPO = "932"
        client.PERIODO_SOLICITADO = ""

    def tearDown(self):
        client.DB = self.old_db
        client.GRUPO = self.old_group
        client.PERIODO_SOLICITADO = self.old_period
        self.tempdir.cleanup()

    def test_sync_replaces_subjects_and_is_idempotent_for_calendar(self):
        client.sincronizar_sqlite(PAYLOAD)
        client.sincronizar_sqlite(PAYLOAD)
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM materias_932").fetchone()[0], 7)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM calendario_932").fetchone()[0], 8)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM horario_cache").fetchone()[0], 1)
            row = connection.execute(
                "SELECT grupo, periodo, payload_json FROM horario_cache"
            ).fetchone()
        self.assertEqual(row[:2], (932, "2026-2"))
        self.assertEqual(json.loads(row[2]), PAYLOAD)
        cached = client.cargar_sqlite_local()
        self.assertEqual(cached["periodo"], "2026-2")
        self.assertEqual(len(cached["materias"]), 7)
        self.assertEqual(cached["materias"][5]["nombre"], "Programación")
        self.assertIn("caché SQLite sincronizada", cached["fuente"])

    def test_offline_does_not_substitute_a_different_requested_period(self):
        client.PERIODO_SOLICITADO = "2027-1"
        with self.assertRaisesRegex(RuntimeError, "no se usó otro periodo"):
            client.cargar_sqlite_local()

    def test_schema_error_rolls_back_and_preserves_existing_subject_row(self):
        with sqlite3.connect(self.database) as connection:
            connection.execute("DROP TABLE materias_932")
            connection.execute("CREATE TABLE materias_932 (materia TEXT PRIMARY KEY)")
            connection.execute("INSERT INTO materias_932 (materia) VALUES ('Respaldo local')")
        with self.assertRaises(sqlite3.DatabaseError):
            client.sincronizar_sqlite(PAYLOAD)
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(
                connection.execute("SELECT materia FROM materias_932").fetchall(),
                [("Respaldo local",)],
            )
            self.assertIsNone(connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='horario_cache'"
            ).fetchone())


if __name__ == "__main__":
    unittest.main()
