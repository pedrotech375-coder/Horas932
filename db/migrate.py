"""Ejecución idempotente de migraciones SQL de Horas 932."""
from __future__ import annotations

from pathlib import Path

from db.mysql import connect_mysql

MIGRATION_TABLE = "horas932_migrations"
MIGRATION_LOCK = "horas932_schema_migrations"
MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def run_migrations() -> None:
    connection = connect_mysql()
    lock_acquired = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT GET_LOCK(%s, 20) AS acquired", (MIGRATION_LOCK,))
            row = cursor.fetchone() or {}
            lock_acquired = int(row.get("acquired") or 0) == 1
            if not lock_acquired:
                raise RuntimeError("No se pudo adquirir el bloqueo de migraciones.")

            cursor.execute(
                f"""CREATE TABLE IF NOT EXISTS `{MIGRATION_TABLE}` (
                    version VARCHAR(191) NOT NULL,
                    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (version)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"""
            )

            for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
                cursor.execute(
                    f"SELECT version FROM `{MIGRATION_TABLE}` WHERE version = %s LIMIT 1",
                    (migration.name,),
                )
                if cursor.fetchone():
                    continue

                sql = migration.read_text(encoding="utf-8")
                statements = [statement.strip() for statement in sql.split(";") if statement.strip()]
                for statement in statements:
                    cursor.execute(statement)
                cursor.execute(
                    f"INSERT IGNORE INTO `{MIGRATION_TABLE}` (version) VALUES (%s)",
                    (migration.name,),
                )
                print(f"Migración aplicada: {migration.name}")
    finally:
        if lock_acquired:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", (MIGRATION_LOCK,))
            except Exception:
                pass
        connection.close()


if __name__ == "__main__":
    run_migrations()
    print("Migraciones completadas.")
