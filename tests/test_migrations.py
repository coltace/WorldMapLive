import os
import sqlite3
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INITIAL_REVISION = "ea0a3061c61f"
EXPECTED_HEAD = "b1a6d4e7c901"


def _upgrade(database_url, revision, env):
    return subprocess.run(
        [sys.executable, "-m", "flask", "--app", "app", "db", "upgrade", revision],
        cwd=PROJECT_ROOT,
        env={**env, "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )


def test_address_migration_preserves_legacy_rows(tmp_path):
    database_path = tmp_path / "legacy.db"
    database_url = f"sqlite:///{database_path}"
    env = {**os.environ, "SECRET_KEY": "migration-test-secret", "FLASK_DEBUG": "false"}

    _upgrade(database_url, INITIAL_REVISION, env)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO users (id, name, email, password_hash, role, is_verified, is_active_account) "
            "VALUES (1, 'Legacy User', 'legacy@example.com', 'hash', 'user', 0, 1)"
        )
        connection.execute(
            "INSERT INTO map_items (id, user_id, name, description, address, category, item_type, "
            "latitude, longitude, status, is_public) VALUES "
            "(1, 1, 'Legacy House', 'Old note', 'Old free-form address', 'home', 'marker', 12.5, -45.5, 'approved', 1)"
        )
        connection.commit()

    _upgrade(database_url, "head", env)
    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(map_items)")}
        row = connection.execute(
            "SELECT name, address, city, country FROM map_items WHERE id=1"
        ).fetchone()
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        indexes = {entry[1] for entry in connection.execute("PRAGMA index_list(map_items)")}

    assert {"house_number", "street", "area", "city", "state", "country", "postal_code"} <= columns
    assert row == ("Legacy House", "Old free-form address", None, None)
    assert revision == EXPECTED_HEAD
    assert {"ix_map_items_public_geo", "ix_map_items_status_geo"} <= indexes
