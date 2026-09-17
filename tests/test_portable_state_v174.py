from __future__ import annotations

import sqlite3
from pathlib import Path

from app.portable_state import auto_import_legacy_database, candidate_count, import_legacy_database


def make_db(path: Path, names: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as con:
        con.execute(
            "CREATE TABLE candidates (name TEXT PRIMARY KEY, domain TEXT NOT NULL, niche TEXT, source TEXT, payload TEXT NOT NULL, decision TEXT NOT NULL DEFAULT 'new', note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        for name in names:
            con.execute(
                "INSERT INTO candidates(name, domain, payload, decision) VALUES(?, ?, '{}', 'shortlist')",
                (name, f"{name}.com"),
            )


def test_import_legacy_database_preserves_existing_empty_target_as_backup(tmp_path):
    source = tmp_path / "old" / "data" / "namelab.db"
    target = tmp_path / "local" / "namelab.db"
    make_db(source, ["lark", "mianem"])
    target.parent.mkdir(parents=True)
    target.write_bytes(b"")

    imported = import_legacy_database(source, target)

    assert imported == target.resolve()
    assert candidate_count(target) == 2
    assert (target.parent / "namelab.before-import.db").exists()


def test_import_refuses_to_overwrite_nonempty_target(tmp_path):
    source = tmp_path / "old.db"
    target = tmp_path / "current.db"
    make_db(source, ["oldname"])
    make_db(target, ["currentname"])

    try:
        import_legacy_database(source, target)
    except ValueError as exc:
        assert "nie jest pusta" in str(exc)
    else:
        raise AssertionError("Expected non-empty target protection")

    assert candidate_count(target) == 1


def test_auto_import_uses_single_obvious_legacy_database(tmp_path):
    launch = tmp_path / "Mianem"
    source = launch / "data" / "namelab.db"
    target = tmp_path / "LocalAppData" / "PMindLab" / "Mianem" / "namelab.db"
    make_db(source, ["savedname"])

    matched = auto_import_legacy_database(launch, target)

    assert matched == source.resolve()
    assert candidate_count(target) == 1
