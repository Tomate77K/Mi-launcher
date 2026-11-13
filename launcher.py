"""Mi Launcher de Minecraft (Java Edition) con perfiles múltiples.

Requiere: pip install minecraft-launcher-lib
Interfaz: Tkinter (viene incluido con Python).
"""

import hashlib
import json
import subprocess
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import minecraft_launcher_lib as mll

LAUNCHER_NAME = "MiLauncher"
LAUNCHER_VERSION = "0.1"

# Carpeta del launcher: configuración, perfiles y archivos compartidos del juego
APP_DIR = Path.home() / ".mi_launcher"
MC_DIR = APP_DIR / "minecraft"          # versiones, librerías, assets y Java (compartidos)
PROFILES_DIR = APP_DIR / "profiles"     # una carpeta de juego por perfil (saves, mods, ...)
CONFIG_FILE = APP_DIR / "config.json"

# Login con Microsoft: el navegador redirige a este puerto local para entregarnos el código.
# En Azure registra como Redirect URI:  http://localhost  (plataforma "Mobile and desktop applications")
# Pega aquí el Application (client) ID de TU app de Azure antes de compartir el launcher.
# Es público (no es una contraseña): tus amigos inician sesión con SU cuenta de Microsoft
# y no necesitan crear nada en Azure. Si lo dejas vacío, el launcher pedirá un Client ID.
DEFAULT_CLIENT_ID = ""

LOGIN_PORT = 8765
REDIRECT_URI = f"http://localhost:{LOGIN_PORT}"
LOGIN_TIMEOUT_S = 180

DEFAULT_PROFILE = {
    "version": "",
    "ram_mb": 2048,
    "jvm_args": "",
}


def offline_uuid(name: str) -> str:
    """UUID de modo offline, igual al que genera el juego para un nombre."""
    h = bytearray(hashlib.md5(f"OfflinePlayer:{name}".encode()).digest())
    h[6] = (h[6] & 0x0F) | 0x30
    h[8] = (h[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(h)))


def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"username": "Jugador", "profiles": {}, "last_profile": None,
            "client_id": "", "account": None}


def save_config(cfg: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


class LauncherApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.cfg = load_config()
        self.versions: list[str] = []
        self.busy = False

        root.title(f"{LAUNCHER_NAME} {LAUNCHER_VERSION}")
        root.geometry("720x420")
        root.minsize(640, 380)

        self._build_ui()
        self._refresh_profile_list()
        threading.Thread(target=self._load_versions, daemon=True).start()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        left = ttk.Frame(self.root, padding=10)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="Perfiles").pack(anchor="w")
        self.listbox = tk.Listbox(left, width=22, exportselection=False)
        self.listbox.pack(fill="y", expand=True, pady=4)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        ttk.Button(left, text="Nuevo", command=self._new_profile).pack(fill="x", pady=1)
        ttk.Button(left, text="Duplicar", command=self._duplicate_profile).pack(fill="x", pady=1)
        ttk.Button(left, text="Eliminar", command=self._delete_profile).pack(fill="x", pady=1)

        right = ttk.Frame(self.root, padding=10)
        right.pack(side="left", fill="both", expand=True)

        acc = ttk.LabelFrame(right, text="Cuenta", padding=10)
        acc.pack(fill="x", pady=(0, 8))
        self.lbl_account = ttk.Label(acc, text="")
        self.lbl_account.pack(side="left")
        self.btn_logout = ttk.Button(acc, text="Cerrar sesión", command=self._logout)
        self.btn_logout.pack(side="right")
        self.btn_login = ttk.Button(acc, text="Iniciar sesión con Microsoft", command=self._login_microsoft)
        self.btn_login.pack(side="right", padx=6)
        if not DEFAULT_CLIENT_ID:
            ttk.Button(acc, text="Client ID…", command=self._ask_client_id).pack(side="right")

        form = ttk.LabelFrame(right, text="Configuración del perfil", padding=10)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        self.var_user = tk.StringVar(value=self.cfg.get("username", "Jugador"))
        self.var_version = tk.StringVar()
        self.var_ram = tk.StringVar(value="2048")
        self.var_jvm = tk.StringVar()
        self.var_show_snap = tk.BooleanVar(value=False)

        ttk.Label(form, text="Nombre de usuario").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(form, textvariable=self.var_user).grid(row=0, column=1, sticky="ew", pady=3)

        ttk.Label(form, text="Versión").grid(row=1, column=0, sticky="w", pady=3)
        self.combo_version = ttk.Combobox(form, textvariable=self.var_version, state="readonly")
        self.combo_version.grid(row=1, column=1, sticky="ew", pady=3)

        ttk.Checkbutton(
            form, text="Mostrar snapshots y versiones antiguas",
            variable=self.var_show_snap, command=self._fill_versions,
        ).grid(row=2, column=1, sticky="w")

        ttk.Label(form, text="RAM (MB)").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Spinbox(form, from_=512, to=32768, increment=512, textvariable=self.var_ram).grid(
            row=3, column=1, sticky="ew", pady=3)

        ttk.Label(form, text="Argumentos JVM extra").grid(row=4, column=0, sticky="w", pady=3)
        ttk.Entry(form, textvariable=self.var_jvm).grid(row=4, column=1, sticky="ew", pady=3)

        btns = ttk.Frame(right)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="Guardar perfil", command=self._save_current).pack(side="left")
        ttk.Button(btns, text="Abrir carpeta del perfil", command=self._open_folder).pack(side="left", padx=6)
        self.btn_play = ttk.Button(btns, text="▶ Jugar", command=self._play)
        self.btn_play.pack(side="right")

        self.progress = ttk.Progressbar(right, mode="determinate")
        self.progress.pack(fill="x", pady=(10, 2))
        self.status = ttk.Label(right, text="Listo")
        self.status.pack(anchor="w")

        self._update_account_ui()

    # --------------------------------------------------------- cuenta Microsoft
    def _update_account_ui(self):
        acc = self.cfg.get("account")
        if acc:
            self.lbl_account.config(text=f"Microsoft: {acc['name']}")
            self.btn_logout.state(["!disabled"])
            self.btn_login.config(text="Cambiar cuenta")
        else:
            self.lbl_account.config(text="Modo offline (sin cuenta)")
            self.btn_logout.state(["disabled"])
            self.btn_login.config(text="Iniciar sesión con Microsoft")

    def _client_id(self) -> str:
        return DEFAULT_CLIENT_ID or self.cfg.get("client_id", "")

    def _ask_client_id(self) -> str:
        cid = simpledialog.askstring(
            "Client ID de Azure",
            "Pega el Application (client) ID de tu app de Azure:",
            initialvalue=self.cfg.get("client_id", ""),
            parent=self.root,
        )
        if cid and cid.strip():
            self.cfg["client_id"] = cid.strip()
            save_config(self.cfg)
        return self.cfg.get("client_id", "")

    def _logout(self):
        self.cfg["account"] = None
        save_config(self.cfg)
        self._update_account_ui()
        self._set_status("Sesión cerrada")

    def _login_microsoft(self):
        if self.busy:
            return
        client_id = self._client_id() or self._ask_client_id()
        if not client_id:
            return
        self.busy = True
        self.btn_login.state(["disabled"])
        self._set_status("Abriendo el navegador para iniciar sesión…")
        threading.Thread(target=self._login_worker, args=(client_id,), daemon=True).start()

    def _login_worker(self, client_id: str):
        ui = self.root.after
        try:
            login_url, state, verifier = mll.microsoft_account.get_secure_login_data(client_id, REDIRECT_URI)

            captured: dict = {}

            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    if "code=" in self.path or "error=" in self.path:
                        captured["url"] = f"{REDIRECT_URI}{self.path}"
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(
                        "<html><body style='font-family:sans-serif;text-align:center;margin-top:15vh'>"
                        "<h2>Listo ✔</h2><p>Ya puedes cerrar esta pestaña y volver al launcher.</p>"
                        "</body></html>".encode("utf-8")
                    )

                def log_message(self, *args):
                    pass

            server = HTTPServer(("localhost", LOGIN_PORT), Handler)
            server.timeout = 5
            webbrowser.open(login_url)

            deadline = time.time() + LOGIN_TIMEOUT_S
            while "url" not in captured and time.time() < deadline:
                server.handle_request()
            server.server_close()

            if "url" not in captured:
                raise RuntimeError("Se agotó el tiempo esperando el inicio de sesión.")

            auth_code = mll.microsoft_account.parse_auth_code_url(captured["url"], state)
            ui(0, lambda: self._set_status("Verificando cuenta con Xbox y Minecraft…"))
            data = mll.microsoft_account.complete_login(client_id, None, REDIRECT_URI, auth_code, verifier)

            self.cfg["account"] = {
                "id": data["id"],
                "name": data["name"],
                "access_token": data["access_token"],
                "refresh_token": data["refresh_token"],
            }
            save_config(self.cfg)
            ui(0, self._update_account_ui)
            ui(0, lambda: self._set_status(f"Sesión iniciada como {data['name']}"))
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            ui(0, lambda: messagebox.showerror("No se pudo iniciar sesión", msg))
            ui(0, lambda: self._set_status("Error al iniciar sesión"))
        finally:
            def done():
                self.busy = False
                self.btn_login.state(["!disabled"])
            ui(0, done)

    def _refresh_account(self) -> dict | None:
        """Renueva el token de la cuenta guardada. Devuelve la cuenta o None si es modo offline."""
        acc = self.cfg.get("account")
        if not acc:
            return None
        data = mll.microsoft_account.complete_refresh(
            self._client_id(), None, REDIRECT_URI, acc["refresh_token"]
        )
        acc = {
            "id": data["id"],
            "name": data["name"],
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
        }
        self.cfg["account"] = acc
        save_config(self.cfg)
        return acc

    # ------------------------------------------------------------ versiones
    def _load_versions(self):
        try:
            data = mll.utils.get_version_list()
        except Exception as e:  # sin internet, etc.
            self.root.after(0, lambda: self._set_status(f"No se pudo obtener la lista de versiones: {e}"))
            data = []
        self._all_versions = data
        self.root.after(0, self._fill_versions)

    def _fill_versions(self):
        data = getattr(self, "_all_versions", [])
        if self.var_show_snap.get():
            ids = [v["id"] for v in data]
        else:
            ids = [v["id"] for v in data if v["type"] == "release"]
        # Añadir también las versiones ya instaladas localmente (Fabric, Forge, etc.)
        try:
            for v in mll.utils.get_installed_versions(str(MC_DIR)):
                if v["id"] not in ids:
                    ids.insert(0, v["id"])
        except Exception:
            pass
        self.versions = ids
        self.combo_version["values"] = ids
        if ids and not self.var_version.get():
            self.var_version.set(ids[0])

    # -------------------------------------------------------------- perfiles
    def _refresh_profile_list(self, select: str | None = None):
        self.listbox.delete(0, "end")
        names = sorted(self.cfg["profiles"])
        for n in names:
            self.listbox.insert("end", n)
        target = select or self.cfg.get("last_profile")
        if target in names:
            idx = names.index(target)
            self.listbox.selection_set(idx)
            self._load_profile(target)

    def _current_name(self) -> str | None:
        sel = self.listbox.curselection()
        return self.listbox.get(sel[0]) if sel else None

    def _on_select(self, _event=None):
        name = self._current_name()
        if name:
            self._load_profile(name)

    def _load_profile(self, name: str):
        p = {**DEFAULT_PROFILE, **self.cfg["profiles"].get(name, {})}
        self.var_version.set(p["version"])
        self.var_ram.set(str(p["ram_mb"]))
        self.var_jvm.set(p["jvm_args"])
        self.cfg["last_profile"] = name

    def _new_profile(self):
        name = simpledialog.askstring("Nuevo perfil", "Nombre del perfil:", parent=self.root)
        if not name or not name.strip():
            return
        name = name.strip()
        if name in self.cfg["profiles"]:
            messagebox.showwarning("Perfil existente", "Ya existe un perfil con ese nombre.")
            return
        self.cfg["profiles"][name] = {**DEFAULT_PROFILE, "version": self.versions[0] if self.versions else ""}
        save_config(self.cfg)
        self._refresh_profile_list(select=name)

    def _duplicate_profile(self):
        name = self._current_name()
        if not name:
            return
        new = simpledialog.askstring("Duplicar perfil", "Nombre del nuevo perfil:", parent=self.root)
        if not new or not new.strip() or new.strip() in self.cfg["profiles"]:
            return
        self.cfg["profiles"][new.strip()] = dict(self.cfg["profiles"][name])
        save_config(self.cfg)
        self._refresh_profile_list(select=new.strip())

    def _delete_profile(self):
        name = self._current_name()
        if not name:
            return
        if messagebox.askyesno(
            "Eliminar perfil",
            f"¿Eliminar el perfil «{name}»?\n(Su carpeta de juego con mundos y mods NO se borra.)",
        ):
            del self.cfg["profiles"][name]
            self.cfg["last_profile"] = None
            save_config(self.cfg)
            self._refresh_profile_list()

    def _save_current(self) -> str | None:
        name = self._current_name()
        if not name:
            messagebox.showinfo("Sin perfil", "Crea o selecciona un perfil primero.")
            return None
        try:
            ram = int(self.var_ram.get())
        except ValueError:
            messagebox.showerror("RAM inválida", "La RAM debe ser un número en MB.")
            return None
        self.cfg["profiles"][name] = {
            "version": self.var_version.get(),
            "ram_mb": ram,
            "jvm_args": self.var_jvm.get().strip(),
        }
        self.cfg["username"] = self.var_user.get().strip() or "Jugador"
        save_config(self.cfg)
        self._set_status(f"Perfil «{name}» guardado")
        return name

    def _game_dir(self, name: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name).strip() or "perfil"
        d = PROFILES_DIR / safe
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _open_folder(self):
        name = self._current_name()
        if not name:
            return
        d = self._game_dir(name)
        import os, sys
        if sys.platform.startswith("win"):
            os.startfile(d)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(d)])
        else:
            subprocess.Popen(["xdg-open", str(d)])

    # ----------------------------------------------------------------- jugar
    def _set_status(self, text: str):
        self.status.config(text=text)

    def _play(self):
        if self.busy:
            return
        name = self._save_current()
        if not name:
            return
        profile = self.cfg["profiles"][name]
        if not profile["version"]:
            messagebox.showwarning("Falta la versión", "Elige una versión de Minecraft.")
            return
        self.busy = True
        self.btn_play.state(["disabled"])
        self.btn_login.state(["disabled"])
        threading.Thread(target=self._install_and_launch, args=(name, profile), daemon=True).start()

    def _install_and_launch(self, name: str, profile: dict):
        ui = self.root.after
        state = {"max": 1}

        callback = {
            "setStatus": lambda t: ui(0, lambda: self._set_status(t)),
            "setMax": lambda m: state.update(max=max(m, 1)),
            "setProgress": lambda v: ui(0, lambda: self.progress.config(maximum=state["max"], value=v)),
        }

        try:
            MC_DIR.mkdir(parents=True, exist_ok=True)
            version = profile["version"]

            # Descarga/verifica versión, librerías, assets y el Java que necesita (si falta)
            mll.install.install_minecraft_version(version, str(MC_DIR), callback=callback)

            # Cuenta Microsoft (renovando el token) o modo offline
            try:
                account = self._refresh_account()
            except Exception as e:
                raise RuntimeError(
                    f"No se pudo renovar tu sesión de Microsoft ({type(e).__name__}). "
                    "Cierra sesión e inicia de nuevo."
                ) from e
            if account:
                username, player_uuid, token = account["name"], account["id"], account["access_token"]
            else:
                username = self.cfg["username"]
                player_uuid, token = offline_uuid(username), ""

            options = {
                "username": username,
                "uuid": player_uuid,
                "token": token,
                "gameDirectory": str(self._game_dir(name)),
                "launcherName": LAUNCHER_NAME,
                "launcherVersion": LAUNCHER_VERSION,
                "jvmArguments": [f"-Xmx{profile['ram_mb']}M", f"-Xms{min(512, profile['ram_mb'])}M"]
                + profile["jvm_args"].split(),
            }
            cmd = mll.command.get_minecraft_command(version, str(MC_DIR), options)

            ui(0, lambda: self._set_status(f"Iniciando Minecraft {version}…"))
            proc = subprocess.Popen(cmd, cwd=options["gameDirectory"])
            proc.wait()
            ui(0, lambda: self._set_status("Minecraft se cerró"))
        except Exception as e:
            msg = str(e)
            ui(0, lambda: messagebox.showerror("Error al iniciar", msg))
            ui(0, lambda: self._set_status("Error"))
        finally:
            def done():
                self.busy = False
                self.btn_play.state(["!disabled"])
                self.btn_login.state(["!disabled"])
                self.progress.config(value=0)
            ui(0, done)


def main():
    root = tk.Tk()
    LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
