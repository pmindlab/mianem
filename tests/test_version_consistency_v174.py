from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path

from app import __version__
from app import main as app_main


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_PATH = ROOT / "packaging" / "windows" / "launcher_windows.py"
SPEC = importlib.util.spec_from_file_location("mianem_windows_launcher_version_test", LAUNCHER_PATH)
assert SPEC is not None and SPEC.loader is not None
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


def test_health_and_ui_render_canonical_version():
    payload = asyncio.run(app_main.health())
    html = asyncio.run(app_main.index())

    assert payload["version"] == __version__
    assert app_main.app.version == __version__
    assert f"Mianem v{__version__}" in html
    assert f"<span>v{__version__}</span>" in html


class _FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_launcher_does_not_reopen_stale_running_version(monkeypatch):
    monkeypatch.setattr(launcher, "PORT_RANGE", range(8787, 8789))

    def fake_urlopen(url: str, timeout: float):
        if ":8787/" in url:
            return _FakeResponse({"ok": True, "app": "Mianem", "version": "1.6"})
        if ":8788/" in url:
            return _FakeResponse({"ok": True, "app": "Mianem", "version": __version__})
        raise AssertionError(url)

    monkeypatch.setattr(launcher.urllib.request, "urlopen", fake_urlopen)

    assert launcher.existing_mianem_port(__version__) == 8788


def test_launcher_can_still_reuse_same_running_version(monkeypatch):
    monkeypatch.setattr(launcher, "PORT_RANGE", range(8787, 8788))
    monkeypatch.setattr(
        launcher.urllib.request,
        "urlopen",
        lambda url, timeout: _FakeResponse({"ok": True, "app": "Mianem", "version": __version__}),
    )

    assert launcher.existing_mianem_port(__version__) == 8787
