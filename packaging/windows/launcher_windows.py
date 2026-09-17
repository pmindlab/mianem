from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path

APP_NAME = "Mianem"
HOST = "127.0.0.1"
PORT_RANGE = range(8787, 8800)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def runtime_dir() -> Path:
    return Path(sys.executable).resolve().parent if is_frozen() else Path(__file__).resolve().parents[2]


def bundle_root() -> Path:
    return Path(getattr(sys, "_MEIPASS")).resolve() if is_frozen() else runtime_dir()


def default_state_dir() -> Path:
    override = os.getenv("MIANEM_STATE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "PMindLab" / APP_NAME
    return Path.home() / ".mianem"


def write_startup_error(exc: Exception, details: str = "") -> Path | None:
    try:
        path = default_state_dir() / "startup-error.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        text = f"{type(exc).__name__}: {exc}\n\n{details or traceback.format_exc()}"
        path.write_text(text, encoding="utf-8")
        return path
    except Exception:
        return None


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def configure_runtime(*, defaults_dir: Path | None = None, state_dir: Path | None = None) -> dict[str, Path]:
    launch_dir = runtime_dir()
    load_env_file(launch_dir / ".env")
    defaults = defaults_dir or (bundle_root() / ("data_defaults" if is_frozen() else "data"))
    state = state_dir or default_state_dir()
    state.mkdir(parents=True, exist_ok=True)
    required = ["profile.json", "niches.json", "language_words.json", "seed_taxa.json"]
    missing = [name for name in required if not (defaults / name).exists()]
    if missing:
        raise RuntimeError(f"Brak danych aplikacji: {', '.join(missing)}")
    os.environ.setdefault("NAMELAB_DB", str(state / "namelab.db"))
    os.environ.setdefault("NAMELAB_CUSTOM_NICHES", str(state / "custom_niches.json"))
    os.environ.setdefault("NAMELAB_PROFILE", str(defaults / "profile.json"))
    os.environ.setdefault("NAMELAB_NICHES", str(defaults / "niches.json"))
    return {"launch_dir": launch_dir, "defaults_dir": defaults, "state_dir": state}


def app_url(port: int) -> str:
    return f"http://{HOST}:{port}"


def existing_mianem_port() -> int | None:
    for port in PORT_RANGE:
        try:
            with urllib.request.urlopen(f"{app_url(port)}/api/health", timeout=0.2) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("ok") is True and payload.get("app") == APP_NAME:
                return port
        except Exception:
            continue
    return None


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((HOST, port))
        except OSError:
            return False
    return True


def choose_port() -> int:
    for port in PORT_RANGE:
        if port_is_free(port):
            return port
    raise RuntimeError("Nie znaleziono wolnego lokalnego portu 8787–8799.")


def make_server(app, port: int):
    import uvicorn

    return uvicorn.Server(
        uvicorn.Config(
            app,
            host=HOST,
            port=port,
            loop="asyncio",
            http="h11",
            ws="none",
            log_config=None,
            access_log=False,
        )
    )


def smoke_test() -> int:
    configure_runtime()
    from app.main import service
    if not service.list_niches() or not service.list_languages():
        raise RuntimeError("Portable smoke test: nie załadowano danych startowych.")
    return 0


def server_smoke_test() -> int:
    configure_runtime()
    port = choose_port()
    from app.main import app

    server = make_server(app, port)
    server_errors: list[tuple[Exception, str]] = []

    def serve() -> None:
        try:
            server.run()
        except Exception as exc:
            server_errors.append((exc, traceback.format_exc()))

    server_thread = threading.Thread(target=serve, name="mianem-server-smoke", daemon=True)
    server_thread.start()
    deadline = time.time() + 12
    try:
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"{app_url(port)}/api/health", timeout=0.4) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if payload.get("ok") is True and payload.get("app") == APP_NAME:
                    return 0
            except Exception:
                if not server_thread.is_alive():
                    break
                time.sleep(0.15)
        if server_errors:
            exc, tb = server_errors[0]
            raise RuntimeError(f"Frozen server failed: {type(exc).__name__}: {exc}\n{tb}") from exc
        raise RuntimeError("Portable server smoke test: lokalny serwer nie osiągnął /api/health.")
    finally:
        server.should_exit = True
        server_thread.join(timeout=5)


def recover_previous_state(paths: dict[str, Path]) -> tuple[Path | None, bool]:
    from packaging.windows.state_migration import auto_import_legacy_database, candidate_count, import_legacy_database

    target_db = Path(os.environ["NAMELAB_DB"])
    if candidate_count(target_db) > 0:
        return None, False

    imported_from = auto_import_legacy_database(paths["launch_dir"], target_db)
    if imported_from:
        return imported_from, True

    import tkinter as tk
    from tkinter import filedialog, messagebox

    root = tk.Tk()
    root.withdraw()
    try:
        wants_import = messagebox.askyesno(
            APP_NAME,
            "Nie znaleziono zapisanych nazw w nowej lokalizacji danych.\n\n"
            "Jeśli używałeś wcześniejszej wersji Mianem, możesz teraz wskazać jej plik data\\namelab.db.\n\n"
            "Zaimportować poprzednie dane?",
            parent=root,
        )
        if not wants_import:
            return None, False
        source = filedialog.askopenfilename(
            title="Wybierz poprzedni plik namelab.db",
            filetypes=[("Baza Mianem", "namelab.db"), ("SQLite", "*.db"), ("Wszystkie pliki", "*.*")],
            parent=root,
        )
        if not source:
            return None, False
        imported = import_legacy_database(source, target_db)
        messagebox.showinfo(
            APP_NAME,
            f"Zaimportowano poprzednie zapisane nazwy.\n\nŹródło: {source}\nNowa baza: {imported}",
            parent=root,
        )
        return Path(source), True
    except Exception as exc:
        messagebox.showerror(
            APP_NAME,
            f"Nie udało się zaimportować poprzednich danych.\n\n{type(exc).__name__}: {exc}\n\n"
            "Żaden istniejący plik nie został nadpisany.",
            parent=root,
        )
        return None, False
    finally:
        root.destroy()


def run_gui() -> int:
    paths = configure_runtime()
    existing = existing_mianem_port()
    if existing is not None:
        webbrowser.open(app_url(existing))
        return 0

    imported_from, imported = recover_previous_state(paths)
    port = choose_port()
    from app import __version__
    from app.main import app
    import tkinter as tk
    from tkinter import messagebox, ttk

    server = make_server(app, port)
    server_errors: list[tuple[Exception, str]] = []

    def serve() -> None:
        try:
            server.run()
        except Exception as exc:
            server_errors.append((exc, traceback.format_exc()))

    server_thread = threading.Thread(target=serve, name="mianem-server", daemon=True)

    root = tk.Tk()
    root.title(f"Mianem {__version__}")
    root.geometry("440x235")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=22)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Mianem", font=("Segoe UI", 20, "bold")).pack(anchor="w")
    initial_status = "Odzyskano poprzednie zapisane dane · uruchamiam…" if imported else "Uruchamiam lokalną aplikację…"
    status = tk.StringVar(value=initial_status)
    ttk.Label(frame, textvariable=status).pack(anchor="w", pady=(9, 4))
    data_text = f"Dane lokalne: {paths['state_dir']}\nInternet jest potrzebny do GBIF i live .com."
    if imported_from:
        data_text += f"\nImport: {imported_from}"
    ttk.Label(frame, text=data_text, justify="left").pack(anchor="w", pady=(0, 16))
    buttons = ttk.Frame(frame)
    buttons.pack(fill="x")
    open_button = ttk.Button(buttons, text="Otwórz Mianem", state="disabled")
    open_button.pack(side="left")
    stop_button = ttk.Button(buttons, text="Zakończ")
    stop_button.pack(side="right")

    url = app_url(port)
    opened = False
    stopping = False

    def open_app() -> None:
        webbrowser.open(url)

    def poll_startup() -> None:
        nonlocal opened
        if server.started:
            status.set(f"Gotowe · {url}")
            open_button.configure(state="normal")
            if not opened:
                opened = True
                open_app()
            return
        if not server_thread.is_alive():
            status.set("Nie udało się uruchomić Mianem.")
            if server_errors:
                exc, tb = server_errors[0]
                log_path = write_startup_error(exc, tb)
                detail = f"{type(exc).__name__}: {exc}"
            else:
                log_path = None
                detail = "Lokalny serwer zakończył pracę podczas startu."
            messagebox.showerror(APP_NAME, f"Nie udało się uruchomić lokalnego serwera Mianem.\n\n{detail}\n\nLog: {log_path or 'niedostępny'}")
            return
        root.after(120, poll_startup)

    def finish_close() -> None:
        if server_thread.is_alive():
            root.after(120, finish_close)
        else:
            root.destroy()

    def stop() -> None:
        nonlocal stopping
        if stopping:
            return
        stopping = True
        status.set("Zamykam Mianem…")
        open_button.configure(state="disabled")
        stop_button.configure(state="disabled")
        server.should_exit = True
        root.after(120, finish_close)

    open_button.configure(command=open_app)
    stop_button.configure(command=stop)
    root.protocol("WM_DELETE_WINDOW", stop)
    server_thread.start()
    root.after(120, poll_startup)
    root.mainloop()
    return 0


def main() -> int:
    smoke = "--smoke-test" in sys.argv
    server_smoke = "--server-smoke-test" in sys.argv
    try:
        if smoke:
            return smoke_test()
        if server_smoke:
            return server_smoke_test()
        return run_gui()
    except Exception as exc:
        if smoke or server_smoke:
            write_startup_error(exc)
            return 1
        return raise_for_gui(exc)


def raise_for_gui(exc: Exception) -> int:
    import tkinter as tk
    from tkinter import messagebox
    log_path = write_startup_error(exc)
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(APP_NAME, f"Mianem nie może się uruchomić.\n\n{type(exc).__name__}: {exc}\n\nLog: {log_path or 'niedostępny'}")
    root.destroy()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
