from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path


def candidate_count(db_path: str | Path) -> int:
    path = Path(db_path)
    if not path.is_file():
        return 0
    try:
        with sqlite3.connect(path) as con:
            row = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='candidates'"
            ).fetchone()
            if not row:
                return 0
            return int(con.execute("SELECT COUNT(*) FROM candidates").fetchone()[0])
    except sqlite3.DatabaseError:
        return 0


def legacy_db_candidates(launch_dir: str | Path, target_db: str | Path) -> list[Path]:
    launch = Path(launch_dir).resolve()
    target = Path(target_db).resolve()
    candidates = [
        launch / "data" / "namelab.db",
        launch.parent / "data" / "namelab.db",
        launch / "namelab.db",
    ]
    out: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved == target or resolved in seen:
            continue
        seen.add(resolved)
        if candidate_count(resolved) > 0:
            out.append(resolved)
    return out


def import_legacy_database(source_db: str | Path, target_db: str | Path) -> Path:
    source = Path(source_db).resolve()
    target = Path(target_db).resolve()
    if candidate_count(source) <= 0:
        raise ValueError("Wybrany plik nie zawiera zapisanych danych Mianem.")
    if candidate_count(target) > 0:
        raise ValueError("Aktualna baza Mianem nie jest pusta; import został zatrzymany, aby niczego nie nadpisać.")

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        backup = target.with_name("namelab.before-import.db")
        suffix = 1
        while backup.exists():
            backup = target.with_name(f"namelab.before-import-{suffix}.db")
            suffix += 1
        shutil.copy2(target, backup)

    temp = target.with_name(f"{target.name}.importing")
    if temp.exists():
        temp.unlink()
    shutil.copy2(source, temp)
    if candidate_count(temp) <= 0:
        temp.unlink(missing_ok=True)
        raise ValueError("Nie udało się zweryfikować importowanej bazy Mianem.")
    temp.replace(target)
    return target


def auto_import_legacy_database(launch_dir: str | Path, target_db: str | Path) -> Path | None:
    if candidate_count(target_db) > 0:
        return None
    matches = legacy_db_candidates(launch_dir, target_db)
    if len(matches) != 1:
        return None
    import_legacy_database(matches[0], target_db)
    return matches[0]
