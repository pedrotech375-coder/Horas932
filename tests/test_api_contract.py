import json
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

import pymysql
from starlette.requests import Request

import main
from db.mysql import MultipleActivePeriods, ScheduleNotFound


SAMPLE = {
    "periodo": "2026-2",
    "grupo": 932,
    "fecha_fin_regular": "2026-11-30",
    "fecha_fin_calculo": "2026-12-11",
    "fechas_adicionales": ["2026-12-09", "2026-12-10", "2026-12-11"],
    "exclusiones": [],
    "materias": [
        {
            "id": 1,
            "nombre": "Programación",
            "horas": {"lunes": 2, "martes": 2, "miercoles": 0, "jueves": 2, "viernes": 0},
            "horas_totales_semana": 6,
        }
    ],
}


def make_request(path="/api/v1/horario", method="GET", query=None):
    query_string = urlencode(query or {}).encode()
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query_string,
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("localhost", 3000),
    })


class ApiContractTests(unittest.TestCase):
    def test_default_group_uses_active_period_and_preserves_json_contract(self):
        with patch.object(main, "fetch_schedule", return_value=SAMPLE) as fetch:
            response = main.schedule(make_request())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.body), SAMPLE)
        self.assertEqual(fetch.call_args.args, (932, None))
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_explicit_period_is_forwarded(self):
        with patch.object(main, "fetch_schedule", return_value=SAMPLE) as fetch:
            response = main.schedule(make_request(query={"grupo": "932", "periodo": "2026-2"}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(fetch.call_args.args, (932, "2026-2"))

    def test_invalid_parameters_do_not_query_mysql(self):
        with patch.object(main, "fetch_schedule") as fetch:
            response = main.schedule(make_request(query={"grupo": "abc", "periodo": "2026-2"}))
        self.assertEqual(response.status_code, 400)
        fetch.assert_not_called()

    def test_missing_schedule_returns_404(self):
        with patch.object(main, "fetch_schedule", side_effect=ScheduleNotFound("No hay periodo.")):
            response = main.schedule(make_request())
        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.body)["error"], "No hay periodo.")

    def test_multiple_active_periods_returns_409(self):
        with patch.object(main, "fetch_schedule", side_effect=MultipleActivePeriods("Conflicto.")):
            response = main.schedule(make_request())
        self.assertEqual(response.status_code, 409)

    def test_mysql_unavailable_returns_generic_503(self):
        with patch.object(main, "fetch_schedule", side_effect=pymysql.MySQLError("private detail")):
            response = main.schedule(make_request())
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private detail", response.body.decode())

    def test_api_rejects_write_methods(self):
        with patch.object(main, "fetch_schedule") as fetch:
            response = main.schedule(make_request(method="POST"))
        self.assertEqual(response.status_code, 405)
        fetch.assert_not_called()

    def test_health_uses_database_and_is_no_store(self):
        with patch.object(main, "ping_database"):
            response = main.health(make_request(path="/api/health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.body), {"status": "ok", "database": "ok"})
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_unknown_api_path_is_json_404(self):
        response = main.unknown_api(make_request(path="/api/v1/no-existe"), "v1/no-existe")
        self.assertEqual(response.status_code, 404)
        self.assertIn("application/json", response.headers["content-type"])


if __name__ == "__main__":
    unittest.main()
