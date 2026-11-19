"""TOMATE77K: launcher de Minecraft (Java Edition) con instancias publicadas por su autor.

El autor publica sus instancias (.mrpack) y una lista (instances.json) en GitHub.
Al abrir el launcher, las instancias aparecen solas como cuadrados; quien lo use
elige una y pulsa Jugar. Se descarga, se instala y se actualiza automáticamente.

Requiere: pip install minecraft-launcher-lib PySide6
Fuente opcional: pon un .ttf estilo Minecraft en una carpeta "fonts" junto a este archivo.
"""

import base64
import colorsys
import copy
import hashlib
import json
import os
import re
import shutil
import ssl
import tempfile
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import (QEasingCurve, QObject, QParallelAnimationGroup, QPoint, QPropertyAnimation,
                            QRectF, QSize, Qt, QTimer, QUrl, Signal)
from PySide6.QtGui import (QColor, QDesktopServices, QFont, QFontDatabase, QIcon, QImage,
                           QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient)
from PySide6.QtWidgets import (QApplication, QColorDialog, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFrame,
                               QGraphicsDropShadowEffect, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit, QProgressBar,
                               QPushButton, QRadioButton, QScrollArea, QSlider, QVBoxLayout,
                               QWidget)

import minecraft_launcher_lib as mll

try:
    import certifi
except ImportError:      # sin certifi se usan los certificados del sistema
    certifi = None


def make_ssl_context() -> ssl.SSLContext:
    """Contexto https con los certificados que lleva el propio launcher (certifi).
    Así funciona también en PCs sin Python instalado, donde faltan certificados."""
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


SSL_CONTEXT = make_ssl_context()

BRAND_NAME = "TOMATE77K"
LAUNCHER_NAME = BRAND_NAME
LAUNCHER_VERSION = "1.14"

# Actualizaciones del propio launcher: un archivo latest.json en el repositorio (ver README).
UPDATE_URL = "https://raw.githubusercontent.com/Tomate77K/Mi-launcher/main/latest.json"
UPDATE_URL_PREFIX = "https://github.com/Tomate77K/"      # el .exe nuevo solo se baja de aquí

# Lista de instancias. Es un archivo instances.json en tu repositorio de GitHub (ver README).
MANIFEST_URL = "https://raw.githubusercontent.com/Tomate77K/Mi-launcher/main/instances.json"

# Carpeta donde se guarda todo: configuración, instancias, juego, logs y caché
APP_DIR = Path.home() / "77K client"
LEGACY_DIR = Path.home() / ".mi_launcher"     # nombre de la versión anterior (se migra sola)
MC_DIR = APP_DIR / "minecraft"          # versiones, librerías, assets y Java (compartidos)
INSTANCES_DIR = APP_DIR / "instances"   # una carpeta por instancia (mods, mundos, config...)
DOWNLOADS_DIR = APP_DIR / "downloads"   # descargas temporales
LOGS_DIR = APP_DIR / "logs"             # latest.log = salida de la última partida
CACHE_DIR = APP_DIR / "cache"           # iconos de instancias y skins
CONFIG_FILE = APP_DIR / "config.json"
MANIFEST_CACHE = APP_DIR / "manifest_cache.json"

# Login con Microsoft: el navegador redirige a este puerto local para entregarnos el código.
# En Azure registra como Redirect URI:  http://localhost  (plataforma "Mobile and desktop applications")
# Es público (no es una contraseña): tus amigos inician sesión con SU cuenta de Microsoft
# y no necesitan crear nada en Azure. Si lo dejas vacío, el launcher pedirá un Client ID.
DEFAULT_CLIENT_ID = "90b784fd-1450-4323-9950-3ee04a0a2829"

LOGIN_PORT = 8765
REDIRECT_URI = f"http://localhost:{LOGIN_PORT}"
LOGIN_TIMEOUT_S = 180

DEFAULT_RAM_MB = 4096
USER_AGENT = f"{BRAND_NAME}/{LAUNCHER_VERSION}"

# Cuenta oficial de Mojang cuya skin es Steve. El launcher descarga su textura de los
# servidores de Mojang (no se incluye ninguna imagen del juego con el launcher).
DEFAULT_SKIN_ACCOUNT = "MHF_Steve"

DEFAULT_CONFIG = {
    "installed": {},            # id -> datos de la instancia instalada
    "ram": {},                  # id -> RAM elegida por el usuario (en MB)
    "last_instance": None,
    "client_id": "",
    "account": None,
    "shortcut_asked": False,    # ya se ofreció crear el acceso directo
    "theme": "#8b2fe0",         # color principal elegido en Personalización
    "theme_style": "vivid",     # vivid (neón), pastel o matte (mate)
}

# ----------------------------------------------------------------- apariencia
DEFAULT_THEME = "#8b2fe0"


PRESETS = (
    ("Neón", "vivid", (("Morado", "#8b2fe0"), ("Celeste", "#22b8e8"), ("Vino", "#b3123f"),
                       ("Esmeralda", "#10b981"), ("Rojo", "#e11d48"))),
    ("Pastel", "pastel", (("Lila", "#b79cff"), ("Rosa", "#ff9ec4"), ("Menta", "#7fe0b8"),
                          ("Cielo", "#8fd0ff"), ("Durazno", "#ffb38a"), ("Limón", "#e8e27a"))),
    ("Mate", "matte", (("Morado", "#7a5c99"), ("Pizarra", "#5b7a99"), ("Salvia", "#7a9a7e"),
                       ("Vino", "#8a4a5a"), ("Arena", "#a89480"), ("Grafito", "#6b6f7a"))),
)


def make_palette(hex_color: str, style: str = "vivid") -> dict:
    """Calcula todos los colores de la interfaz a partir de un color y un estilo
    (vivid = neón, pastel = suave y claro, matte = apagado)."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = (int(h[k:k + 2], 16) / 255 for k in (0, 2, 4))
    except (ValueError, IndexError):
        return make_palette(DEFAULT_THEME, style)
    hue, light, sat = colorsys.rgb_to_hls(r, g, b)

    def col(l, s_, hh=hue):
        rr, gg, bb = colorsys.hls_to_rgb(hh, max(0.0, min(1.0, l)), max(0.0, min(1.0, s_)))
        return (round(rr * 255), round(gg * 255), round(bb * 255))

    def hx(c):
        return "#%02x%02x%02x" % c

    def rgb(c):
        return "%d, %d, %d" % c

    if style == "pastel":
        l, s_ = 0.78, 0.70
        bg_bottom, bg_glow, li = col(0.50, 0.42), col(0.72, 0.65), col(0.82, 0.70)
        btn_text = hx(col(0.12, 0.45))             # texto oscuro sobre el pastel claro
    elif style == "matte":
        l, s_ = 0.46, min(max(sat, 0.06), 0.42)
        bg_bottom, bg_glow, li = col(0.24, s_), col(0.42, s_), col(0.70, s_)
        btn_text = "#ffffff"
    else:
        l, s_ = min(max(light, 0.32), 0.62), sat    # evita acentos casi negros o casi blancos
        bg_bottom, bg_glow, li = col(0.30, sat), col(0.50, sat), col(0.72, sat)
        btn_text = "#ffffff"

    accent = col(l, s_)
    dlg = col(0.08, s_ * 0.6)
    return {
        "ACCENT": hx(accent),
        "ACCENT_HOVER": hx(col(l + 0.07, s_)),
        "ACCENT_PRESSED": hx(col(l - 0.08, s_)),
        "ACCENT_DISABLED": hx(col(0.22, s_ * 0.4)),
        "DIS_TEXT": hx(col(0.50, s_ * 0.3)),
        "TEXT": hx(col(0.95, s_ * 0.8)),
        "MUTED": hx(col(0.74, s_ * 0.5)),
        "SUB": hx(col(0.80, s_ * 0.7)),
        "BTN_TEXT": btn_text,
        "AC": rgb(accent),
        "LI": rgb(li),
        "DK": rgb(col(0.06, s_ * 0.6)),
        "DLG": hx(dlg),
        "MENU": hx(col(0.11, s_ * 0.6)),
        # No son textos de la hoja de estilo: los usan el fondo, el brillo y los diálogos
        "bg_bottom": bg_bottom,
        "bg_glow": bg_glow,
        "title_glow": col(0.60, s_),
        "dlg_rgb": dlg,
        "li_rgb": li,
    }


QSS = """
QWidget { color: @TEXT@; font-size: 14px; }
QLabel { background: transparent; }
QLabel#title { font-weight: @BOLD@; }
QLabel#head { font-size: 17px; font-weight: @BOLD@; }
QLabel#muted { color: @MUTED@; font-size: 13px; }

QFrame#card {
    background-color: rgba(@DK@, 175);
    border: 1px solid rgba(@LI@, 70);
    border-radius: 30px;
}

QPushButton {
    background-color: @ACCENT@; color: @BTN_TEXT@; border: none; border-radius: 20px;
    padding: 12px 28px; font-weight: @BOLD@; min-height: 20px;
}
QPushButton:hover { background-color: @ACCENT_HOVER@; }
QPushButton:pressed { background-color: @ACCENT_PRESSED@; }
QPushButton:disabled { background-color: @ACCENT_DISABLED@; color: @DIS_TEXT@; }
QPushButton[variant="ghost"] { background-color: rgba(255, 255, 255, 18); color: @TEXT@; padding: 12px 26px;
    border: none; border-radius: 20px; }
QPushButton[variant="ghost"]:checked { background-color: @ACCENT@; color: @BTN_TEXT@; }
QPushButton[variant="ghost"]:hover { background-color: rgba(255, 255, 255, 36); }
QPushButton[variant="ghost"]:disabled { background-color: rgba(255, 255, 255, 8); color: @DIS_TEXT@; }
QPushButton#play { padding: 13px 38px; font-size: 16px; }
QPushButton#gear { background-color: rgba(255, 255, 255, 22); border-radius: 25px; padding: 0; font-size: 30px; }
QPushButton#gear:hover { background-color: @ACCENT@; }
QPushButton#more { background-color: rgba(255, 255, 255, 18); border-radius: 17px; padding: 0; font-size: 22px; }
QPushButton#more:hover { background-color: rgba(255, 255, 255, 40); }
QPushButton#avatar {
    background-color: rgba(255, 255, 255, 22); border: 1px solid rgba(@LI@, 80);
    border-radius: 20px; padding: 0;
}
QPushButton#avatar:hover { background-color: rgba(255, 255, 255, 44); }

QPushButton#tile {
    background-color: rgba(@AC@, 55); border: 2px solid transparent;
    border-radius: 22px; padding: 0; font-size: 26px; color: @TEXT@;
}
QPushButton#tile:hover { background-color: rgba(@AC@, 115); }
QPushButton#tile:checked { border: 2px solid @ACCENT_HOVER@; }

QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }

QProgressBar { background-color: rgba(255, 255, 255, 24); border: none; border-radius: 4px; }
QProgressBar::chunk { background-color: @ACCENT@; border-radius: 4px; }

QLineEdit, QDoubleSpinBox {
    background-color: rgba(255, 255, 255, 18); border: 1px solid rgba(@LI@, 70);
    border-radius: 16px; padding: 9px 14px; selection-background-color: @ACCENT@;
}
QListWidget { background: transparent; border: none; outline: none; color: @TEXT@; }
QListWidget::item { border-radius: 18px; padding: 8px; margin: 3px; color: @TEXT@; }
QListWidget::item:hover { background-color: rgba(255, 255, 255, 16); }
QListWidget::item:selected { background-color: rgba(@AC@, 110); color: @TEXT@; }
QComboBox {
    background-color: rgba(255, 255, 255, 18); border: 1px solid rgba(@LI@, 70);
    border-radius: 16px; padding: 9px 14px; color: @TEXT@;
}
QComboBox::drop-down { border: none; width: 28px; }
QComboBox QAbstractItemView {
    background-color: @MENU@; color: @TEXT@; border: 1px solid rgba(@LI@, 90);
    border-radius: 12px; padding: 6px; outline: none; selection-background-color: @ACCENT@;
    selection-color: @BTN_TEXT@;
}
QLabel#value {
    background-color: rgba(255, 255, 255, 18); border: 1px solid rgba(@LI@, 70);
    border-radius: 16px; padding: 9px 14px; font-weight: @BOLD@;
}
QSlider::groove:horizontal { height: 8px; background: rgba(255, 255, 255, 30); border-radius: 4px; }
QSlider::sub-page:horizontal { background: @ACCENT@; border-radius: 4px; }
QSlider::handle:horizontal { width: 22px; height: 22px; margin: -8px 0; border-radius: 11px; background: #ffffff; }

QDialog { background: transparent; }
QMessageBox, QInputDialog { background-color: @DLG@; }
QPlainTextEdit {
    background-color: #0a0612; border: 1px solid rgba(@LI@, 70); border-radius: 18px;
    padding: 10px; font-family: Consolas, "Courier New", monospace; font-size: 12px;
}
QRadioButton { spacing: 10px; padding: 4px 0; }

QMenu { background-color: @MENU@; border: 1px solid rgba(@LI@, 90); border-radius: 20px; padding: 8px; }
QMenu::item { padding: 10px 22px 10px 12px; margin: 1px 0; border-radius: 13px; }
QMenu::icon { padding-left: 8px; }
QMenu::separator { height: 1px; background: rgba(255, 255, 255, 28); margin: 6px 14px; }
QMenu::item:selected { background-color: @ACCENT@; }
QMenu::item:disabled { color: @DIS_TEXT@; }

QToolTip {
    background-color: @MENU@; color: @TEXT@; border: 1px solid rgba(@LI@, 90);
    padding: 6px 10px;
}

QScrollBar:horizontal { background: transparent; height: 8px; margin: 1px; }
QScrollBar::handle:horizontal { background: rgba(@LI@, 110); border-radius: 3px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(@LI@, 110); border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""

# Fuentes estilo Minecraft que se usan si están instaladas o en la carpeta "fonts"
FONT_CANDIDATES = ("poppins", "monocraft", "minecraft", "minecraftia", "minecrafter")


def build_qss(pixel_font: bool, pal: dict) -> str:
    values = {k: v for k, v in pal.items() if isinstance(v, str)}
    values["BOLD"] = "normal" if pixel_font else "bold"   # las fuentes pixeladas se ven mal en negrita
    qss = QSS
    for key, val in values.items():
        qss = qss.replace(f"@{key}@", val)
    return qss


def resource_path(rel: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / rel


def load_fonts() -> tuple[str, bool]:
    """Registra las fuentes de la carpeta fonts/ y devuelve (familia, es_pixelada)."""
    fonts_dir = resource_path("fonts")
    loaded: list[str] = []
    if fonts_dir.is_dir():
        for f in sorted(list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf"))):
            font_id = QFontDatabase.addApplicationFont(str(f))
            if font_id != -1:
                loaded += QFontDatabase.applicationFontFamilies(font_id)
    available = loaded + list(QFontDatabase.families())
    for cand in FONT_CANDIDATES:
        for fam in available:
            if fam.lower().startswith(cand):
                return fam, cand != "poppins"      # solo las fuentes pixeladas llevan ajustes
    return "", False


class Background(QWidget):
    """Fondo de la ventana: degradado vertical (negro arriba, color del tema abajo).
    El marco, los botones de cerrar/minimizar y el icono son los normales de Windows."""

    bg_bottom = (96, 30, 150)
    bg_glow = (150, 60, 220)

    def paintEvent(self, _event):
        p = QPainter(self)
        rect = QRectF(self.rect())
        grad = QLinearGradient(0, rect.top(), 0, rect.bottom())
        grad.setColorAt(0.0, QColor(0, 0, 0))
        grad.setColorAt(0.30, QColor(0, 0, 0))
        grad.setColorAt(1.0, QColor(*self.bg_bottom))
        p.fillRect(rect, grad)

        # brillo suave y simétrico en la parte baja
        glow = QRadialGradient(rect.center().x(), rect.bottom() + 20, rect.width() * 0.7)
        glow.setColorAt(0.0, QColor(*self.bg_glow, 80))
        glow.setColorAt(1.0, QColor(*self.bg_glow, 0))
        p.fillRect(rect, glow)
        p.end()


class TileButton(QPushButton):
    """Cuadrado de instancia. Gris mientras no está instalada; al descargarse se va llenando
    de color de abajo hacia arriba."""

    accent = QColor(162, 77, 240)       # color del borde de selección (lo fija el tema)

    def __init__(self):
        super().__init__()
        self._progress = -1.0       # -1 = a todo color; 0 = todo gris; entre 0 y 1 = descargando

    def set_progress(self, value: float):
        self._progress = value
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        gray = 0.0 <= self._progress < 1.0
        if not gray and not self.isChecked():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        if gray:
            clip = QPainterPath()
            clip.addRoundedRect(rect, 22, 22)
            p.save()
            p.setClipPath(clip)
            gray_h = self.height() * (1.0 - self._progress)
            p.fillRect(QRectF(0, 0, self.width(), gray_h), QColor(70, 70, 76, 185))
            p.restore()
        if self.isChecked():                # el borde de selección siempre queda por encima
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(self.accent, 2))
            p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 21, 21)
        p.end()


# ------------------------------------------------------------------ imágenes
def rounded_pixmap(src: QPixmap, size: int, radius: int, smooth: bool = True) -> QPixmap:
    """Recorta la imagen a un cuadrado con esquinas redondeadas."""
    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(0, 0, size, size, radius, radius)
    p.setClipPath(clip)
    mode = (Qt.TransformationMode.SmoothTransformation if smooth
            else Qt.TransformationMode.FastTransformation)
    scaled = src.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, mode)
    p.drawPixmap((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
    p.end()
    return out


def head_pixmap(skin_path: str, size: int, radius: int | None = None) -> QPixmap | None:
    """Cabeza (cara + capa de sombrero) de un archivo de skin de Minecraft."""
    skin = QImage(skin_path)
    if skin.isNull() or skin.width() < 64 or skin.height() < 16:
        return None
    k = skin.width() // 64          # 1 en skins normales, 2 en skins HD
    face = skin.copy(8 * k, 8 * k, 8 * k, 8 * k).convertToFormat(QImage.Format.Format_ARGB32)
    hat = skin.copy(40 * k, 8 * k, 8 * k, 8 * k).convertToFormat(QImage.Format.Format_ARGB32)
    p = QPainter(face)
    p.drawImage(0, 0, hat)
    p.end()
    return rounded_pixmap(QPixmap.fromImage(face), size, size // 2 if radius is None else radius, smooth=False)


def body_pixmap(skin_path: str, height: int, slim: bool = False) -> QPixmap | None:
    """Skin de cuerpo entero, vista de frente (con las capas exteriores), dibujada pixel a pixel."""
    skin = QImage(skin_path)
    if skin.isNull() or skin.width() < 64 or skin.height() < 32:
        return None
    skin = skin.convertToFormat(QImage.Format.Format_ARGB32)
    k = skin.width() // 64
    modern = skin.height() >= 64 * k
    aw = 3 if slim else 4
    canvas = QImage(16 * k, 32 * k, QImage.Format.Format_ARGB32)
    canvas.fill(0)
    p = QPainter(canvas)

    def part(sx, sy, w, h, dx, dy, mirror=False):
        piece = skin.copy(sx * k, sy * k, w * k, h * k)
        if mirror:
            piece = piece.mirrored(True, False)
        p.drawImage(dx * k, dy * k, piece)

    part(8, 8, 8, 8, 4, 0)                                        # cabeza
    part(20, 20, 8, 12, 4, 8)                                     # torso
    part(44, 20, aw, 12, 4 - aw, 8)                               # brazo derecho (a la izquierda del dibujo)
    part(4, 20, 4, 12, 4, 20)                                     # pierna derecha
    if modern:
        part(36, 52, aw, 12, 12, 8)                               # brazo izquierdo
        part(20, 52, 4, 12, 8, 20)                                # pierna izquierda
        part(40, 8, 8, 8, 4, 0)                                   # sombrero
        part(20, 36, 8, 12, 4, 8)                                 # chaqueta
        part(44, 36, aw, 12, 4 - aw, 8)                           # manga derecha
        part(52, 52, aw, 12, 12, 8)                               # manga izquierda
        part(4, 36, 4, 12, 4, 20)                                 # pantalón derecho
        part(4, 52, 4, 12, 8, 20)                                 # pantalón izquierdo
    else:                                                         # skins antiguas: izquierda = espejo
        part(44, 20, aw, 12, 12, 8, mirror=True)
        part(4, 20, 4, 12, 8, 20, mirror=True)
        part(40, 8, 8, 8, 4, 0)
    p.end()
    pix = QPixmap.fromImage(canvas)
    return pix.scaledToHeight(height, Qt.TransformationMode.FastTransformation)


def cape_pixmap(cape_path: str, height: int) -> QPixmap | None:
    """Parte de atrás de una capa (la que se ve), ampliada sin suavizar."""
    img = QImage(cape_path)
    if img.isNull() or img.width() < 64 or img.height() < 32:
        return None
    k = img.width() // 64
    back = img.copy(1 * k, 1 * k, 10 * k, 16 * k)
    return QPixmap.fromImage(back).scaledToHeight(height, Qt.TransformationMode.FastTransformation)


def silhouette_pixmap(size: int) -> QPixmap:
    """Silueta genérica (dibujo propio) mientras carga el avatar o si no hay conexión."""
    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(0, 0, size, size, size // 4, size // 4)
    p.setClipPath(clip)
    p.fillPath(clip, QColor(255, 255, 255, 28))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(190, 160, 235))
    r = int(size * 0.18)
    p.drawEllipse(size // 2 - r, int(size * 0.20), 2 * r, 2 * r)
    p.drawEllipse(int(size * 0.20), int(size * 0.62), int(size * 0.60), int(size * 0.60))
    p.end()
    return out


# ------------------------------------------------------------------ utilidades
def migrate_legacy_dir() -> None:
    """Si existe la carpeta de la versión anterior y la nueva no, se renombra (conserva todo)."""
    if LEGACY_DIR.exists() and not APP_DIR.exists():
        try:
            LEGACY_DIR.rename(APP_DIR)
        except OSError:
            pass


def load_config() -> dict:
    loaded: dict = {}
    if CONFIG_FILE.exists():
        try:
            loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            loaded = {}
    cfg = {**copy.deepcopy(DEFAULT_CONFIG), **loaded}
    cfg.pop("mode", None)          # versiones anteriores tenían modo offline (ya no existe)
    cfg.pop("username", None)
    return cfg


def save_config(cfg: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def slugify(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(name)).strip("_") or "instancia"


def icon_path(iid: str) -> Path:
    return CACHE_DIR / "icons" / f"{slugify(iid)}.png"


def parse_manifest(data) -> list[dict]:
    """Valida instances.json y devuelve solo las entradas correctas."""
    entries = []
    items = data.get("instances", []) if isinstance(data, dict) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = str(item.get("mrpack_url", ""))
        if not item.get("id") or not item.get("name") or not url.startswith("https://"):
            continue
        icon_url = str(item.get("icon_url", ""))
        entries.append({
            "id": slugify(item["id"]),            # se usa como nombre de carpeta
            "name": str(item["name"]),
            "summary": str(item.get("summary", "")),
            "version": str(item.get("version", "1")),
            "mrpack_url": url,
            "icon_url": icon_url if icon_url.startswith("https://") else "",
            "sha256": str(item.get("sha256", "")).lower(),
            "ram_mb": int(item.get("ram_mb", DEFAULT_RAM_MB)),
        })
    return entries


def pick_skin_url(login_data: dict) -> str:
    """URL de la skin activa en los datos devueltos por el login de Microsoft."""
    skins = login_data.get("skins") or []
    active = [s for s in skins if str(s.get("state", "")).upper() == "ACTIVE"]
    chosen = (active or skins or [None])[0]
    return str(chosen.get("url", "")) if chosen else ""


SKINS_DIR = APP_DIR / "skins"           # biblioteca de skins de cada cuenta
_LIB_LOCK = threading.Lock()


def lib_dir(acc_id: str) -> Path:
    return SKINS_DIR / slugify(acc_id)


def lib_load(acc_id: str) -> list[dict]:
    """Skins guardadas de la cuenta: [{sha, name, variant, file}]."""
    try:
        data = json.loads((lib_dir(acc_id) / "index.json").read_text(encoding="utf-8"))
        return [e for e in data if (lib_dir(acc_id) / e.get("file", "")).exists()]
    except (OSError, json.JSONDecodeError):
        return []


def pixel_key(png: bytes) -> str:
    """Huella de los píxeles de la imagen. Mojang vuelve a codificar los PNG, así que los bytes
    de la skin subida y los de la descargada no coinciden aunque la imagen sea la misma."""
    try:
        img = QImage.fromData(png)
        if not img.isNull():
            img = img.convertToFormat(QImage.Format.Format_ARGB32)
            raw = bytes(img.constBits())
            return hashlib.sha1(f"{img.width()}x{img.height()}".encode() + raw).hexdigest()
    except Exception:
        pass
    return hashlib.sha1(png).hexdigest()


def lib_dedupe(acc_id: str) -> None:
    """Quita de la biblioteca las skins repetidas (misma imagen), conservando la que tiene nombre propio."""
    groups: dict = {}
    for e in lib_load(acc_id):
        try:
            key = pixel_key((lib_dir(acc_id) / e["file"]).read_bytes())
        except OSError:
            continue
        groups.setdefault(key, []).append(e)
    for dup in groups.values():
        if len(dup) > 1:
            keep = next((e for e in dup if e.get("name") != "Skin original"), dup[0])
            for e in dup:
                if e is not keep:
                    lib_remove(acc_id, e["sha"])


def lib_add(acc_id: str, png: bytes, name: str, variant: str) -> bool:
    """Guarda una skin en la biblioteca (si ya estaba, no se duplica). Devuelve True si era nueva."""
    sha = pixel_key(png)
    with _LIB_LOCK:
        items = lib_load(acc_id)
        for e in items:
            try:
                if e["sha"] == sha or pixel_key((lib_dir(acc_id) / e["file"]).read_bytes()) == sha:
                    return False
            except OSError:
                continue
        folder = lib_dir(acc_id)
        folder.mkdir(parents=True, exist_ok=True)
        fname = f"{sha[:16]}.png"
        (folder / fname).write_bytes(png)
        items.append({"sha": sha, "name": (name or "Skin")[:40], "variant": variant, "file": fname})
        (folder / "index.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        return True


def lib_remove(acc_id: str, sha: str) -> None:
    with _LIB_LOCK:
        items = lib_load(acc_id)
        keep = [e for e in items if e["sha"] != sha]
        for e in items:
            if e["sha"] == sha:
                try:
                    (lib_dir(acc_id) / e["file"]).unlink()
                except OSError:
                    pass
        (lib_dir(acc_id) / "index.json").write_text(json.dumps(keep, ensure_ascii=False, indent=1), encoding="utf-8")


MC_API = "https://api.minecraftservices.com"


def mc_api(method: str, path: str, token: str, body: bytes | None = None,
           content_type: str = "application/json", timeout: int = 30) -> dict:
    """Llama a la API de perfil de Minecraft con el token de la cuenta del propio jugador."""
    headers = {"User-Agent": USER_AGENT, "Authorization": f"Bearer {token}", "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(MC_API + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT) as resp:
            raw = resp.read().decode("utf-8") or "{}"
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read().decode("utf-8")).get("errorMessage", "")
        except Exception:
            pass
        raise RuntimeError(f"Minecraft respondió {e.code}. {detail}".strip()) from e
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def skin_multipart(variant: str, png: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    head = (f'--{boundary}\r\nContent-Disposition: form-data; name="variant"\r\n\r\n{variant}\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="skin.png"\r\n'
            f'Content-Type: image/png\r\n\r\n').encode()
    return head + png + f"\r\n--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


def fetch_json(url: str, timeout: int = 15):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_small(url: str, dest: Path, host: str | None = None, max_bytes: int = 2_000_000) -> Path:
    """Descarga un archivo pequeño (icono, skin). Solo https; con host fijo si se indica."""
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    parsed = urlparse(url)
    if parsed.scheme != "https" or (host and parsed.hostname != host):
        raise ValueError("URL no permitida")
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15, context=SSL_CONTEXT) as resp:
        data = resp.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("archivo demasiado grande")
    dest.write_bytes(data)
    return dest


def default_skin() -> Path:
    """Skin de Steve, descargada una vez de los servidores de Mojang y guardada en caché."""
    dest = CACHE_DIR / "skins" / "default.png"
    if dest.exists():
        return dest
    profile = fetch_json(f"https://api.mojang.com/users/profiles/minecraft/{DEFAULT_SKIN_ACCOUNT}")
    session = fetch_json(f"https://sessionserver.mojang.com/session/minecraft/profile/{profile['id']}")
    for prop in session.get("properties", []):
        if prop.get("name") == "textures":
            textures = json.loads(base64.b64decode(prop["value"]))
            url = textures["textures"]["SKIN"]["url"]
            return download_small(url, dest, host="textures.minecraft.net")
    raise RuntimeError("No se encontró la skin")


def download_file(url: str, dest: Path, cb: dict, sha256: str = "") -> None:
    """Descarga url en dest informando el progreso. Verifica sha256 si se indicó."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as resp, open(dest, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        cb["setMax"](total or 1)
        done = 0
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            if total:
                cb["setProgress"](done)
    if sha256 and digest.hexdigest() != sha256:
        dest.unlink(missing_ok=True)
        raise RuntimeError("La descarga no coincide con el sha256 del catálogo (archivo corrupto o cambiado).")


JAVA_RUNTIMES = ("java-runtime-delta", "java-runtime-gamma")     # Java 21 y Java 17 de Mojang


def ensure_java(cb: dict) -> None:
    """Algunos instaladores (Forge, NeoForge) ejecutan Java mientras instalan. En un PC sin Java
    fallaría con «FileNotFoundError». Se descarga el Java de Mojang y se pone al principio del PATH."""
    for name in JAVA_RUNTIMES:
        try:
            exe = mll.runtime.get_executable_path(name, str(MC_DIR))
            if not exe:
                cb["setStatus"]("Preparando Java…")
                mll.runtime.install_jvm_runtime(name, str(MC_DIR), callback=cb)
                exe = mll.runtime.get_executable_path(name, str(MC_DIR))
            if exe:
                java_dir = str(Path(exe).parent)
                paths = os.environ.get("PATH", "").split(os.pathsep)
                if java_dir not in paths:
                    os.environ["PATH"] = java_dir + os.pathsep + os.environ.get("PATH", "")
                return
        except Exception as e:
            cb["setStatus"](f"No se pudo preparar {name} ({type(e).__name__})")


def parse_version(value) -> tuple:
    return tuple(int(n) for n in re.findall(r"\d+", str(value)))


def parse_update(data) -> dict | None:
    """Valida latest.json. Solo se acepta un .exe alojado en tu cuenta de GitHub."""
    if not isinstance(data, dict):
        return None
    url = str(data.get("url", ""))
    version = str(data.get("version", ""))
    if not version or not url.startswith(UPDATE_URL_PREFIX):
        return None
    installer = str(data.get("installer_url", ""))
    return {
        "version": version, "url": url, "sha256": str(data.get("sha256", "")).lower(),
        # El instalador es lo que usan las versiones nuevas; url/sha256 quedan para las antiguas
        "installer_url": installer if installer.startswith(UPDATE_URL_PREFIX) else "",
        "installer_sha256": str(data.get("installer_sha256", "")).lower(),
    }


def installed_with_installer() -> bool:
    """True si el programa se instaló con TOMATE77K-setup.exe (junto al .exe está el desinstalador)."""
    folders = {Path(__file__).resolve().parent, Path(sys.argv[0]).resolve().parent}
    return is_frozen() and any((d / "unins000.exe").exists() for d in folders)


def is_frozen() -> bool:
    """True en el programa compilado (Nuitka marca __compiled__; PyInstaller marca sys.frozen)."""
    return "__compiled__" in globals() or bool(getattr(sys, "frozen", False))


class PillButton(QPushButton):
    """Botón secundario dibujado a mano: siempre es una píldora perfecta (o un círculo si es cuadrado).
    Las hojas de estilo de Qt no redondeaban bien estos botones, así que se pintan directamente."""

    accent = QColor(139, 47, 224)
    text_color = QColor(243, 235, 255)
    on_accent = QColor(255, 255, 255)

    def __init__(self, text: str = "", hover_accent: bool = False):
        super().__init__(text)
        self.hover_accent = hover_accent
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        return QSize(fm.horizontalAdvance(self.text()) + 54, max(46, fm.height() + 26))

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            fill = QColor(255, 255, 255, 8)
        elif self.isChecked():
            fill = self.accent
        elif self.isDown():
            fill = QColor(255, 255, 255, 60)
        elif self.underMouse():
            fill = self.accent if self.hover_accent else QColor(255, 255, 255, 40)
        else:
            fill = QColor(255, 255, 255, 20)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        p.setBrush(fill)
        radius = min(rect.width(), rect.height()) / 2
        p.drawRoundedRect(rect, radius, radius)
        if not self.isEnabled():
            p.setPen(QColor(255, 255, 255, 90))
        elif self.isChecked() or (self.hover_accent and self.underMouse()):
            p.setPen(self.on_accent)
        else:
            p.setPen(self.text_color)
        p.setFont(self.font())
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        p.end()


def make_button(text: str, ghost: bool = False, name: str = "") -> QPushButton:
    if ghost or name in ("gear", "more"):
        btn: QPushButton = PillButton(text, hover_accent=(name == "gear"))
        if name:
            btn.setObjectName(name)
        return btn
    btn = QPushButton(text)
    if name:
        btn.setObjectName(name)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def play_open_animation(widget: QWidget, dy: int, ms: int) -> None:
    """Aparece con fundido y un pequeño deslizamiento hacia su posición final."""
    end = widget.pos()
    widget.setWindowOpacity(0.0)
    fade = QPropertyAnimation(widget, b"windowOpacity", widget)
    fade.setDuration(ms)
    fade.setStartValue(0.0)
    fade.setEndValue(1.0)
    fade.setEasingCurve(QEasingCurve.Type.OutCubic)
    slide = QPropertyAnimation(widget, b"pos", widget)
    slide.setDuration(ms)
    slide.setStartValue(end + QPoint(0, dy))
    slide.setEndValue(end)
    spring = QEasingCurve(QEasingCurve.Type.OutBack)      # pasa un poco y vuelve, como un resorte
    spring.setOvershoot(1.6)
    slide.setEasingCurve(spring)
    group = QParallelAnimationGroup(widget)
    group.addAnimation(fade)
    group.addAnimation(slide)
    widget._open_anim = group          # se guarda para que no lo borre el recolector
    group.start()


class FadeMenu(QMenu):
    """Menú que se abre con una animación suave."""

    def showEvent(self, event):
        super().showEvent(event)
        play_open_animation(self, 14, 300)


class FadeDialog(QDialog):
    """Diálogo que se abre con una animación suave."""

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_shown_once", False):
            self._shown_once = True
            play_open_animation(self, 26, 380)

    def hideEvent(self, event):
        self._shown_once = False       # la próxima vez que se abra, vuelve a animarse
        super().hideEvent(event)


class RoundedDialog(FadeDialog):
    """Diálogo sin marco, con esquinas redondeadas y sombra, a juego con la ventana principal."""

    MARGIN = 22
    RADIUS = 28
    surface = QColor(18, 10, 31, 245)       # los fija el tema
    edge = QColor(170, 100, 255, 80)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def pad(self, left: int, top: int, right: int, bottom: int) -> tuple:
        m = self.MARGIN
        return (left + m, top + m, right + m, bottom + m)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        m, r = self.MARGIN, self.RADIUS
        rect = QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(1, m - 3):
            alpha = int(70 * (1 - i / (m - 3)) ** 2)
            p.setPen(QPen(QColor(0, 0, 0, alpha), 1))
            p.drawRoundedRect(rect.adjusted(-i, -i + 4, i, i + 4), r + i, r + i)
        p.setPen(QPen(self.edge, 1))
        p.setBrush(self.surface)
        p.drawRoundedRect(rect, r, r)
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.windowHandle() is not None:
            self.windowHandle().startSystemMove()
        super().mousePressEvent(event)


class MessageDialog(RoundedDialog):
    def __init__(self, parent, title: str, text: str, yes: str = "Aceptar", no: str = ""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(*self.pad(30, 28, 30, 24))
        lay.setSpacing(12)
        head = QLabel(title)
        head.setObjectName("head")
        body = QLabel(text)
        body.setWordWrap(True)
        body.setObjectName("muted")
        buttons = QHBoxLayout()
        buttons.addStretch()
        if no:
            cancel = make_button(no, ghost=True)
            cancel.clicked.connect(self.reject)
            buttons.addWidget(cancel)
        ok = make_button(yes)
        ok.clicked.connect(self.accept)
        ok.setDefault(True)
        buttons.addWidget(ok)
        lay.addWidget(head)
        lay.addWidget(body)
        lay.addSpacing(8)
        lay.addLayout(buttons)


def show_message(parent, title: str, text: str) -> None:
    MessageDialog(parent, title, text).exec()


def confirm(parent, title: str, text: str, yes: str = "Sí", no: str = "No") -> bool:
    return MessageDialog(parent, title, text, yes, no).exec() == QDialog.DialogCode.Accepted


ICON_FONTS = ("Segoe Fluent Icons", "Segoe MDL2 Assets")     # iconos que trae Windows 10/11


def glyph_icon(code: int, color: QColor) -> QIcon:
    """Icono pequeño para los menús, dibujado con la fuente de iconos de Windows."""
    families = set(QFontDatabase.families())
    family = next((f for f in ICON_FONTS if f in families), "")
    if not family:
        return QIcon()
    pm = QPixmap(32, 32)
    pm.setDevicePixelRatio(2.0)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    font = QFont(family)
    font.setPixelSize(14)
    p.setFont(font)
    p.setPen(color)
    p.drawText(QRectF(0, 0, 16, 16), Qt.AlignmentFlag.AlignCenter, chr(code))
    p.end()
    return QIcon(pm)


def style_menu(menu: QMenu) -> None:
    """Menú con esquinas redondeadas (ventana sin marco y fondo translúcido)."""
    menu.setWindowFlags(menu.windowFlags()
                        | Qt.WindowType.FramelessWindowHint
                        | Qt.WindowType.NoDropShadowWindowHint)
    menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)


class Bus(QObject):
    """Señales para que los hilos de trabajo hablen con la interfaz sin tocarla directamente."""
    status = Signal(str)
    percent = Signal(int)
    busy = Signal(bool)
    catalog = Signal(str)        # id a seleccionar ("" = el último usado)
    account = Signal()
    avatar = Signal(str)         # ruta de la skin para el avatar ("" = silueta)
    error = Signal(str, str)     # título, mensaje
    log = Signal(str)
    upd_progress = Signal(int)
    upd_done = Signal(str)                  # "" = bien; si no, el error


# --------------------------------------------------------------------- diálogos
class RamDialog(RoundedDialog):
    def __init__(self, parent, name: str, mb: int):
        super().__init__(parent)
        self.setWindowTitle("Memoria RAM")
        self.setModal(True)
        self.setMinimumWidth(440)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*self.pad(28, 26, 28, 22))
        lay.setSpacing(14)

        head = QLabel("Memoria RAM")
        head.setObjectName("head")
        sub = QLabel(f"Para «{name}»")
        sub.setObjectName("muted")

        row = QHBoxLayout()
        row.setSpacing(16)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(2, 64)                   # en medios GB: 1 a 32 GB
        self.value_lbl = QLabel()                     # muestra el valor elegido
        self.value_lbl.setObjectName("value")
        self.value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_lbl.setFixedWidth(110)
        gb = max(1.0, min(32.0, mb / 1024))
        self.slider.setValue(int(round(gb * 2)))
        self.slider.valueChanged.connect(self._show_value)
        self._show_value(self.slider.value())
        row.addWidget(self.slider, 1)
        row.addWidget(self.value_lbl)

        hint = QLabel("Para la mayoría de modpacks, entre 4 y 6 GB va bien. "
                      "No uses casi toda la RAM de tu PC.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)

        buttons = QHBoxLayout()
        cancel = make_button("Cancelar", ghost=True)
        save = make_button("Guardar")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.accept)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(save)

        lay.addWidget(head)
        lay.addWidget(sub)
        lay.addLayout(row)
        lay.addWidget(hint)
        lay.addSpacing(6)
        lay.addLayout(buttons)

    def _show_value(self, value: int):
        self.value_lbl.setText(f"{value / 2:g} GB")

    def megabytes(self) -> int:
        return int(round(self.slider.value() / 2 * 1024))


class UpdateDialog(RoundedDialog):
    def __init__(self, parent, version: str):
        super().__init__(parent)
        self.setWindowTitle("Actualización")
        self.setModal(True)
        self.setMinimumWidth(400)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(*self.pad(28, 26, 28, 24))
        lay.setSpacing(14)
        head = QLabel(f"Actualizando a la versión {version}")
        head.setObjectName("head")
        note = QLabel("Se abrirá solo cuando termine. No cierres esta ventana.")
        note.setObjectName("muted")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        lay.addWidget(head)
        lay.addWidget(note)
        lay.addWidget(self.bar)

    def reject(self):          # no se puede cerrar con Esc a mitad de la descarga
        pass


class ThemeDialog(RoundedDialog):
    """Personalización simple: paletas listas (neón, pastel y mate) y, si quieres, otro color."""

    def __init__(self, main: "MainWindow"):
        super().__init__(main)
        self.main = main
        self.setWindowTitle("Personalización")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.swatches: list = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*self.pad(30, 28, 30, 24))
        lay.setSpacing(10)
        head = QLabel("Personalización")
        head.setObjectName("head")
        lay.addWidget(head)

        for title, style, colors in PRESETS:
            label = QLabel(title)
            label.setObjectName("muted")
            lay.addSpacing(6)
            lay.addWidget(label)
            row = QHBoxLayout()
            row.setSpacing(12)
            for name, hex_color in colors:
                btn = QPushButton()
                btn.setFixedSize(40, 40)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setToolTip(name)
                shade = make_palette(hex_color, style)["ACCENT"]
                btn.setProperty("swatch", (hex_color, style, shade))
                btn.clicked.connect(lambda _c=False, h=hex_color, st=style: self._pick(h, st))
                self.swatches.append(btn)
                row.addWidget(btn)
            row.addStretch()
            lay.addLayout(row)

        buttons = QHBoxLayout()
        other = make_button("Otro color…", ghost=True)
        other.clicked.connect(self._other)
        done = make_button("Listo")
        done.clicked.connect(self.accept)
        buttons.addWidget(other)
        buttons.addStretch()
        buttons.addWidget(done)
        lay.addSpacing(12)
        lay.addLayout(buttons)
        self._refresh()

    def _refresh(self):
        cfg = self.main.cfg
        for btn in self.swatches:
            hex_color, style, shade = btn.property("swatch")
            chosen = hex_color.lower() == cfg.get("theme", "").lower() and style == cfg.get("theme_style")
            ring = "#ffffff" if chosen else "transparent"
            btn.setStyleSheet(f"QPushButton {{ background-color: {shade}; border: 3px solid {ring};"
                              f" border-radius: 18px; padding: 0; }}")

    def _pick(self, hex_color: str, style: str):
        self.main.set_theme(hex_color, style)
        self._refresh()

    def _other(self):
        color = QColorDialog.getColor(QColor(self.main.cfg.get("theme", DEFAULT_THEME)), self, "Elige un color")
        if color.isValid():
            self.main.set_theme(color.name(), "vivid")
            self._refresh()


def _list_widget(icon_w: int, icon_h: int, cell_w: int, cell_h: int) -> QListWidget:
    lw = QListWidget()
    lw.setViewMode(QListWidget.ViewMode.IconMode)
    lw.setIconSize(QSize(icon_w, icon_h))
    lw.setGridSize(QSize(cell_w, cell_h))
    lw.setResizeMode(QListWidget.ResizeMode.Adjust)
    lw.setMovement(QListWidget.Movement.Static)
    lw.setWrapping(True)
    lw.setWordWrap(True)
    lw.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
    lw.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    lw.setFixedHeight(cell_h * 2 + 8)
    lw.setFrameShape(QFrame.Shape.NoFrame)
    return lw


class CapeDialog(RoundedDialog):
    """Elegir entre las capas oficiales que ya tiene la cuenta (no se pueden añadir otras)."""

    loaded = Signal(object, object, str)      # perfil, {id: ruta de la imagen}, error
    applied = Signal(str)                     # "" = bien; si no, el error

    def __init__(self, main: "MainWindow"):
        super().__init__(main)
        self.main = main
        self.setWindowTitle("Capas")
        self.setModal(True)
        self.setMinimumWidth(560)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*self.pad(28, 26, 28, 22))
        lay.setSpacing(10)
        head = QLabel("Capas")
        head.setObjectName("head")
        self.lbl = QLabel("Cargando tus capas…")
        self.lbl.setObjectName("muted")
        self.lbl.setWordWrap(True)
        self.grid = _list_widget(64, 104, 118, 168)
        self.grid.hide()

        buttons = QHBoxLayout()
        self.btn_apply = make_button("Usar esta capa")
        self.btn_apply.setEnabled(False)
        close = make_button("Cerrar", ghost=True)
        close.clicked.connect(self.accept)
        self.btn_apply.clicked.connect(self._apply)
        buttons.addStretch()
        buttons.addWidget(close)
        buttons.addWidget(self.btn_apply)

        lay.addWidget(head)
        lay.addWidget(self.lbl)
        lay.addWidget(self.grid)
        lay.addSpacing(8)
        lay.addLayout(buttons)

        self.loaded.connect(self._on_loaded)
        self.applied.connect(self._on_applied)
        threading.Thread(target=self._load_worker, daemon=True).start()

    def _emit(self, signal, *args):
        try:
            signal.emit(*args)
        except RuntimeError:
            pass                      # el diálogo ya se cerró

    def _load_worker(self):
        try:
            token = self.main._refresh_account()["access_token"]
            profile = mc_api("GET", "/minecraft/profile", token)
            paths: dict = {}
            for cape in profile.get("capes") or []:
                try:
                    dest = CACHE_DIR / "capes" / f"{slugify(cape.get('id', 'capa'))}.png"
                    if not dest.exists():
                        download_small(str(cape.get("url", "")), dest, host="textures.minecraft.net")
                    paths[str(cape.get("id", ""))] = str(dest)
                except Exception:
                    pass              # sin imagen: se muestra solo el nombre
            self._emit(self.loaded, profile, paths, "")
        except Exception as e:
            self._emit(self.loaded, None, {}, f"{type(e).__name__}: {e}")

    def _on_loaded(self, profile, paths: dict, error: str):
        if error or profile is None:
            self.lbl.setText(f"No se pudieron cargar tus capas.\n{error}")
            return
        capes = profile.get("capes") or []
        if not capes:
            self.lbl.setText("Tu cuenta no tiene capas oficiales. Las capas las entrega Mojang "
                             "(eventos, promociones, etc.); el launcher no puede añadirlas.")
            return
        self.lbl.setText("Elige la capa que quieres usar:")
        self.grid.show()
        self.grid.clear()
        none = QListWidgetItem("Sin capa")
        none.setData(Qt.ItemDataRole.UserRole, "")
        none.setIcon(QIcon(silhouette_pixmap(64)))
        self.grid.addItem(none)
        active_item = none
        for cape in capes:
            cid = str(cape.get("id", ""))
            name = str(cape.get("alias") or "Capa")
            active = str(cape.get("state", "")).upper() == "ACTIVE"
            item = QListWidgetItem(("✓ " if active else "") + name)
            item.setData(Qt.ItemDataRole.UserRole, cid)
            pix = cape_pixmap(paths.get(cid, ""), 104) if cid in paths else None
            if pix:
                item.setIcon(QIcon(pix))
            self.grid.addItem(item)
            if active:
                active_item = item
        self.grid.setCurrentItem(active_item)
        self.btn_apply.setEnabled(True)

    def _apply(self):
        item = self.grid.currentItem()
        if item is None:
            return
        self.btn_apply.setEnabled(False)
        self.lbl.setText("Aplicando…")
        threading.Thread(target=self._apply_worker, args=(item.data(Qt.ItemDataRole.UserRole),),
                         daemon=True).start()

    def _apply_worker(self, cape_id: str):
        try:
            token = self.main._refresh_account()["access_token"]
            if cape_id:
                mc_api("PUT", "/minecraft/profile/capes/active", token,
                       json.dumps({"capeId": cape_id}).encode("utf-8"))
            else:
                mc_api("DELETE", "/minecraft/profile/capes/active", token)
            self._emit(self.applied, "")
        except Exception as e:
            self._emit(self.applied, f"{type(e).__name__}: {e}")

    def _on_applied(self, error: str):
        self.btn_apply.setEnabled(True)
        if error:
            self.lbl.setText(f"No se pudo cambiar la capa.\n{error}")
        else:
            self.lbl.setText("Capa actualizada. Se verá la próxima vez que entres al juego.")


class SkinNameDialog(RoundedDialog):
    """Nombre y modelo de la skin que se va a subir."""

    def __init__(self, parent, number: int):
        super().__init__(parent)
        self.setWindowTitle("Nueva skin")
        self.setModal(True)
        self.setMinimumWidth(400)
        self._default = f"Skin {number}"

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*self.pad(28, 26, 28, 22))
        lay.setSpacing(14)
        head = QLabel("Nueva skin")
        head.setObjectName("head")
        self.ed = QLineEdit()
        self.ed.setPlaceholderText(f"Nombre (si lo dejas vacío: {self._default})")
        self.ed.setMaxLength(24)

        self.rb_classic = make_button("Clásico", ghost=True)
        self.rb_slim = make_button("Slim", ghost=True)
        for b in (self.rb_classic, self.rb_slim):
            b.setCheckable(True)
        self.rb_classic.setChecked(True)
        self.rb_classic.clicked.connect(lambda: self.rb_slim.setChecked(False) or self.rb_classic.setChecked(True))
        self.rb_slim.clicked.connect(lambda: self.rb_classic.setChecked(False) or self.rb_slim.setChecked(True))
        models = QHBoxLayout()
        models.addWidget(self.rb_classic)
        models.addWidget(self.rb_slim)
        models.addStretch()

        cancel = make_button("Cancelar", ghost=True)
        ok = make_button("Subir")
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self.accept)
        ok.setDefault(True)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(ok)

        lay.addWidget(head)
        lay.addWidget(self.ed)
        lay.addLayout(models)
        lay.addSpacing(4)
        lay.addLayout(buttons)

    def name(self) -> str:
        return self.ed.text().strip() or self._default

    def variant(self) -> str:
        return "slim" if self.rb_slim.isChecked() else "classic"


class SkinsDialog(RoundedDialog):
    """Biblioteca de skins de la cuenta: guarda la que tenías y las que vas subiendo."""

    refreshed = Signal()

    def __init__(self, main: "MainWindow"):
        super().__init__(main)
        self.main = main
        self.acc_id = (main.cfg.get("account") or {}).get("id", "")
        self.setWindowTitle("Skins")
        self.setModal(True)
        self.setMinimumWidth(520)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*self.pad(28, 26, 28, 22))
        lay.setSpacing(10)
        head = QLabel("Skins")
        head.setObjectName("head")
        self.grid = _list_widget(64, 128, 118, 176)

        self.btn_new = make_button("+ Subir", ghost=True)
        self.btn_use = make_button("Usar")
        self.btn_del = make_button("Quitar", ghost=True)
        self.btn_new.clicked.connect(self._new)
        self.btn_use.clicked.connect(self._use)
        self.btn_del.clicked.connect(self._remove)
        row = QHBoxLayout()
        row.addWidget(self.btn_new)
        row.addWidget(self.btn_del)
        row.addStretch()
        row.addWidget(self.btn_use)
        close = make_button("Cerrar", ghost=True)
        close.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(close)

        lay.addWidget(head)
        lay.addWidget(self.grid)
        lay.addLayout(row)
        lay.addSpacing(4)
        lay.addLayout(bottom)

        lib_dedupe(self.acc_id)
        self.refreshed.connect(self._fill)
        self.main.bus.account.connect(self._on_account)
        self.main.bus.busy.connect(self._on_busy)
        self._fill()
        threading.Thread(target=self._save_current_worker, daemon=True).start()

    def _emit_refresh(self):
        try:
            self.refreshed.emit()
        except RuntimeError:
            pass

    def _save_current_worker(self):
        """Guarda en la biblioteca la skin que la cuenta tiene puesta ahora (si aún no estaba)."""
        try:
            token = self.main._refresh_account()["access_token"]
            profile = mc_api("GET", "/minecraft/profile", token)
            skins = profile.get("skins") or []
            active = ([k for k in skins if str(k.get("state", "")).upper() == "ACTIVE"] or skins or [None])[0]
            if not active or not active.get("url"):
                return
            tmp = CACHE_DIR / "skins" / f"{slugify(self.acc_id)}_actual.png"
            download_small(str(active["url"]), tmp, host="textures.minecraft.net")
            variant = "slim" if str(active.get("variant", "")).upper() == "SLIM" else "classic"
            if lib_add(self.acc_id, tmp.read_bytes(), "Skin original", variant):
                self._emit_refresh()
        except Exception:
            pass

    def _fill(self):
        self.grid.clear()
        items = lib_load(self.acc_id)
        current = (self.main.cfg.get("account") or {}).get("skin_url", "")
        for e in items:
            path = str(lib_dir(self.acc_id) / e["file"])
            pix = body_pixmap(path, 128, slim=e.get("variant") == "slim")
            item = QListWidgetItem(e.get("name", "Skin"))
            item.setData(Qt.ItemDataRole.UserRole, e)
            if pix:
                item.setIcon(QIcon(pix))
            self.grid.addItem(item)
        if self.grid.count():
            self.grid.setCurrentRow(0)
        self.btn_use.setEnabled(bool(items) and not self.main.busy)
        self.btn_del.setEnabled(bool(items))

    def _on_account(self):
        self._fill()

    def _on_busy(self, *_):
        self.btn_new.setEnabled(not self.main.busy)
        self.btn_use.setEnabled(self.grid.count() > 0 and not self.main.busy)

    def _new(self):
        path, _ = QFileDialog.getOpenFileName(self, "Elige tu skin (PNG)", str(Path.home()), "Imagen PNG (*.png)")
        if not path:
            return
        img = QImage(path)
        if img.isNull() or (img.width(), img.height()) not in ((64, 64), (64, 32)):
            show_message(self, "Skin no válida", "La skin debe ser un PNG de 64×64 o 64×32 píxeles.")
            return
        dlg = SkinNameDialog(self, len(lib_load(self.acc_id)) + 1)
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        name, variant = dlg.name(), dlg.variant()
        dlg.deleteLater()
        if ok:
            self.main._upload_skin(path, variant, name=name)

    def _use(self):
        item = self.grid.currentItem()
        if item is None:
            return
        e = item.data(Qt.ItemDataRole.UserRole)
        self.main._upload_skin(str(lib_dir(self.acc_id) / e["file"]), e.get("variant", "classic"), name=e.get("name", ""))

    def _remove(self):
        item = self.grid.currentItem()
        if item is None:
            return
        e = item.data(Qt.ItemDataRole.UserRole)
        if confirm(self, "Quitar de la biblioteca",
                   f"¿Quitar «{e.get('name', 'Skin')}» de tu biblioteca?\n\nNo cambia la skin que tienes puesta en Minecraft.",
                   yes="Quitar", no="Cancelar"):
            lib_remove(self.acc_id, e["sha"])
            self._fill()


class AccountDialog(RoundedDialog):
    """Cuenta de Microsoft (hace falta Minecraft Java para jugar) y apariencia: skin y capa."""

    def __init__(self, main: "MainWindow"):
        super().__init__(main)
        self.main = main
        self.setWindowTitle("Cuenta")
        self.setModal(True)
        self.setMinimumWidth(500)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*self.pad(28, 26, 28, 22))
        lay.setSpacing(12)

        head = QLabel("Cuenta de Microsoft")
        head.setObjectName("head")
        self.lbl_acc = QLabel()
        self.lbl_acc.setObjectName("muted")
        self.note = QLabel("Para jugar necesitas una cuenta de Microsoft que tenga Minecraft Java Edition. "
                           "El inicio de sesión se hace en la página oficial de Microsoft.")
        self.note.setObjectName("muted")
        self.note.setWordWrap(True)

        self.btn_login = make_button("Iniciar sesión con Microsoft", ghost=True)
        self.btn_logout = make_button("Cerrar sesión", ghost=True)
        self.btn_login.clicked.connect(self.main._login_microsoft)
        self.btn_logout.clicked.connect(self.main._logout)
        acc_row = QHBoxLayout()
        acc_row.addWidget(self.btn_login)
        acc_row.addWidget(self.btn_logout)
        acc_row.addStretch()

        # ---- apariencia (solo con sesión iniciada)
        self.look = QWidget()
        look_lay = QVBoxLayout(self.look)
        look_lay.setContentsMargins(0, 6, 0, 0)
        look_lay.setSpacing(10)
        look_head = QLabel("Apariencia")
        look_head.setObjectName("muted")
        self.btn_skin = make_button("Skins…", ghost=True)
        self.btn_capes = make_button("Capas…", ghost=True)
        self.btn_skin.clicked.connect(self._open_skins)
        self.btn_capes.clicked.connect(self._open_capes)
        look_row = QHBoxLayout()
        look_row.addWidget(self.btn_skin)
        look_row.addWidget(self.btn_capes)
        look_row.addStretch()
        look_lay.addWidget(look_head)
        look_lay.addLayout(look_row)

        buttons = QHBoxLayout()
        close = make_button("Cerrar")
        close.clicked.connect(self.accept)
        buttons.addStretch()
        buttons.addWidget(close)

        lay.addWidget(head)
        lay.addWidget(self.lbl_acc)
        lay.addLayout(acc_row)
        lay.addWidget(self.note)
        lay.addWidget(self.look)
        lay.addSpacing(8)
        lay.addLayout(buttons)

        self.main.bus.account.connect(self.refresh)
        self.main.bus.busy.connect(self.refresh)
        self.refresh()

    def refresh(self, *_):
        acc = self.main.cfg.get("account")
        busy = self.main.busy
        self.lbl_acc.setText(f"Sesión iniciada: {acc['name']}" if acc else "Sin sesión de Microsoft")
        self.btn_login.setVisible(not acc)            # con sesión no hay «cambiar de cuenta»
        self.btn_logout.setVisible(bool(acc))
        self.note.setVisible(not acc)
        self.look.setVisible(bool(acc))
        self.btn_login.setEnabled(not busy)
        self.btn_logout.setEnabled(not busy)
        self.btn_skin.setEnabled(not busy)
        self.btn_capes.setEnabled(not busy)

    def _open_skins(self):
        dlg = SkinsDialog(self.main)
        dlg.exec()
        dlg.deleteLater()

    def _open_capes(self):
        dlg = CapeDialog(self.main)
        dlg.exec()
        dlg.deleteLater()


class LogsDialog(RoundedDialog):
    def __init__(self, main: "MainWindow"):
        super().__init__(main)
        self.main = main
        self.setWindowTitle("Logs")
        self.resize(830, 550)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(*self.pad(22, 20, 22, 18))
        lay.setSpacing(12)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(5000)
        self.view.setPlainText("\n".join(main.log_lines))
        self._scroll_to_end()

        buttons = QHBoxLayout()
        copy_btn = make_button("Copiar todo", ghost=True)
        folder_btn = make_button("Abrir carpeta de logs", ghost=True)
        close_btn = make_button("Cerrar")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.view.toPlainText()))
        folder_btn.clicked.connect(self._open_folder)
        close_btn.clicked.connect(self.close)
        buttons.addWidget(copy_btn)
        buttons.addWidget(folder_btn)
        buttons.addStretch()
        buttons.addWidget(close_btn)

        lay.addWidget(self.view, 1)
        lay.addLayout(buttons)

        main.bus.log.connect(self.add_line)

    def _scroll_to_end(self):
        bar = self.view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def add_line(self, line: str):
        bar = self.view.verticalScrollBar()
        at_end = bar.value() >= bar.maximum() - 4
        self.view.appendPlainText(line)
        if at_end:
            self._scroll_to_end()

    def _open_folder(self):
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOGS_DIR)))


# ------------------------------------------------------------------ ventana
class MainWindow(Background):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.remote: list[dict] = []          # entradas del catálogo (en línea o caché)
        self.catalog: dict[str, dict] = {}    # id -> entrada
        self.ids: list[str] = []              # instancias en el orden de la columna
        self.current: str | None = None       # instancia seleccionada
        self.installing: str | None = None    # instancia que se está descargando
        self.game_running = False             # Minecraft abierto (no se actualiza el launcher)
        self.tiles: dict[str, QPushButton] = {}
        self.busy = False
        self.log_lines: deque = deque(maxlen=5000)
        self.logs_dialog: LogsDialog | None = None
        self.bus = Bus()

        self.setWindowTitle("CLIENT77K")      # título de la ventana (el nombre grande de dentro es BRAND_NAME)
        icon_file = resource_path("icon.ico")
        if icon_file.exists():
            self.setWindowIcon(QIcon(str(icon_file)))
        self.setMinimumSize(760, 500)              # marco normal de Windows: se puede agrandar, achicar y maximizar
        self.resize(960, 600)

        self._build_ui()
        self.apply_theme(self.cfg.get("theme", DEFAULT_THEME), self.cfg.get("theme_style", "vivid"))

        self.bus.status.connect(self._on_status)
        self.bus.percent.connect(self._on_percent)
        self.bus.busy.connect(self._apply_busy)
        self.bus.catalog.connect(self._rebuild_catalog)
        self.bus.error.connect(self._show_error)
        self.bus.log.connect(self._store_log)
        self.bus.avatar.connect(self._set_avatar)
        self.bus.account.connect(self._update_avatar)

        self._set_avatar("")                  # silueta mientras carga el avatar
        self._load_cached_manifest()
        self._rebuild_catalog()
        self._update_avatar()
        self._fetch_catalog()

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_intro_done", False):
            self._intro_done = True
            intro = QPropertyAnimation(self, b"windowOpacity", self)
            intro.setDuration(450)
            intro.setStartValue(0.0)
            intro.setEndValue(1.0)
            intro.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.setWindowOpacity(0.0)
            self._intro_anim = intro
            intro.start()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 22, 32, 28)
        root.setSpacing(14)

        # ---- barra superior: nombre a la izquierda y la tuerca
        top = QHBoxLayout()
        title = QLabel()
        title.setObjectName("title")
        title.setTextFormat(Qt.TextFormat.RichText)
        self.lbl_title = title
        self.title_glow = QGraphicsDropShadowEffect(title)
        self.title_glow.setBlurRadius(36)
        self.title_glow.setOffset(0, 0)
        title.setGraphicsEffect(self.title_glow)

        self.btn_gear = make_button("⚙", name="gear")
        self.btn_gear.setFixedSize(58, 58)
        self.btn_gear.clicked.connect(self._show_gear_menu)

        # nombre a la izquierda, alineado con la columna de instancias; la tuerca a la derecha,
        # los dos centrados en la misma fila
        top.addWidget(title, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addStretch()
        top.addWidget(self.btn_gear, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(top)

        # ---- cuerpo: columna de instancias a la izquierda (llega hasta abajo, al nivel de
        #      Jugar y el avatar) y, a la derecha, un espacio libre con Jugar y el avatar abajo
        body = QHBoxLayout()
        body.setSpacing(18)
        root.addLayout(body, 1)

        column = QFrame()
        column.setObjectName("card")
        column.setFixedWidth(98)
        col_lay = QVBoxLayout(column)
        col_lay.setContentsMargins(14, 14, 14, 14)
        col_lay.setSpacing(10)

        self.tiles_area = QScrollArea()
        self.tiles_area.setWidgetResizable(True)
        self.tiles_area.setFrameShape(QFrame.Shape.NoFrame)
        self.tiles_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tiles_host = QWidget()
        self.tiles_lay = QVBoxLayout(self.tiles_host)
        self.tiles_lay.setContentsMargins(0, 0, 0, 0)
        self.tiles_lay.setSpacing(12)
        self.tiles_area.setWidget(self.tiles_host)

        self.btn_more = make_button("⋯", ghost=True, name="more")
        self.btn_more.setFixedSize(64, 38)
        self.btn_more.clicked.connect(self._show_more_menu)

        col_lay.addWidget(self.tiles_area, 1)
        col_lay.addWidget(self.btn_more, 0, Qt.AlignmentFlag.AlignHCenter)
        body.addWidget(column)

        right = QVBoxLayout()
        right.addStretch(1)
        bottom = QHBoxLayout()
        bottom.setSpacing(14)

        self.btn_play = make_button("Jugar", name="play")
        self.btn_play.clicked.connect(self._play)

        self.btn_avatar = make_button("", name="avatar")
        self.btn_avatar.setFixedSize(72, 72)
        self.btn_avatar.setIconSize(QSize(60, 60))
        self.btn_avatar.clicked.connect(self._open_account)

        bottom.addStretch(1)
        bottom.addWidget(self.btn_play, 0, Qt.AlignmentFlag.AlignVCenter)
        bottom.addWidget(self.btn_avatar, 0, Qt.AlignmentFlag.AlignVCenter)
        right.addLayout(bottom)
        body.addLayout(right, 1)

        # ---- menú de la tuerca
        self.gear_menu = FadeMenu(self.btn_gear)
        style_menu(self.gear_menu)
        soft = QColor(235, 225, 250, 220)
        danger = QColor(255, 125, 135)
        self.gear_menu.addAction(glyph_icon(0xE8A5, soft), "Logs").triggered.connect(self._open_logs)
        self.gear_menu.addAction(glyph_icon(0xE9E9, soft), "Memoria RAM (GB)").triggered.connect(self._open_ram)
        self.gear_menu.addSeparator()
        self.gear_menu.addAction(glyph_icon(0xE790, soft), "Personalización").triggered.connect(self._open_theme)


        # ---- menú de los tres puntos (instancias)
        self.more_menu = FadeMenu(self.btn_more)
        style_menu(self.more_menu)
        self.act_refresh = self.more_menu.addAction(glyph_icon(0xE72C, soft), "Actualizar lista")
        self.act_folder = self.more_menu.addAction(glyph_icon(0xE838, soft), "Abrir carpeta")
        self.more_menu.addSeparator()
        self.act_uninstall = self.more_menu.addAction(glyph_icon(0xE74D, danger), "Desinstalar")
        self.act_refresh.triggered.connect(self._fetch_catalog)
        self.act_folder.triggered.connect(self._open_folder)
        self.act_uninstall.triggered.connect(self._uninstall)

    def _show_gear_menu(self):
        width = self.gear_menu.sizeHint().width()
        pos = self.btn_gear.mapToGlobal(QPoint(self.btn_gear.width() - width, self.btn_gear.height() + 8))
        self.gear_menu.exec(pos)

    def _show_more_menu(self):
        height = self.more_menu.sizeHint().height()
        pos = self.btn_more.mapToGlobal(QPoint(self.btn_more.width() + 12, self.btn_more.height() - height))
        self.more_menu.exec(pos)

    # ---------------------------------------------------------- señales / estado
    def _on_status(self, text: str):
        self.bus.log.emit(f"[{LAUNCHER_NAME}] {text}")

    def _store_log(self, line: str):
        self.log_lines.append(line)

    def _show_error(self, title: str, message: str):
        show_message(self, title, message)

    def _apply_busy(self, busy: bool):
        self.busy = busy
        for w in (self.btn_play, self.act_refresh, self.act_uninstall):
            w.setEnabled(not busy)

    def _make_callback(self) -> dict:
        """Callbacks de progreso. El instalador tiene varias etapas (cada setMax empieza una);
        se combinan en un único avance que nunca retrocede."""
        state = {"max": 1, "stage": -1, "frac": 0.0}

        def emit():
            k = max(state["stage"], 0)
            overall = 1.0 - (0.6 ** k) * (1.0 - 0.4 * state["frac"])
            self.bus.percent.emit(min(99, int(overall * 100)))

        def set_max(m):
            state["max"] = max(int(m), 1)
            state["stage"] += 1
            state["frac"] = 0.0
            emit()

        def set_progress(v):
            state["frac"] = min(1.0, int(v) / state["max"])
            emit()

        return {
            "setStatus": lambda t: self.bus.status.emit(str(t)),
            "setMax": set_max,
            "setProgress": set_progress,
        }

    def _base_progress(self, iid: str) -> float:
        """Gris completo (0) si la instancia no está instalada; color normal (-1) si lo está."""
        return 0.0 if self.cfg["installed"].get(iid) is None else -1.0

    def _on_percent(self, value: int):
        iid = self.installing
        tile = self.tiles.get(iid) if iid else None
        if tile is not None:
            tile.set_progress(value / 100 if value >= 0 else self._base_progress(iid))
        if value < 0 or value >= 100:
            self.installing = None

    # ------------------------------------------------------------ tema
    def apply_theme(self, hex_color: str, style: str = "vivid"):
        if not QColor(hex_color).isValid():
            hex_color = DEFAULT_THEME
        pal = make_palette(QColor(hex_color).name(), style)
        TileButton.accent = QColor(pal["ACCENT_HOVER"])
        PillButton.accent = QColor(pal["ACCENT"])
        PillButton.text_color = QColor(pal["TEXT"])
        PillButton.on_accent = QColor(pal["BTN_TEXT"])
        RoundedDialog.surface = QColor(*pal["dlg_rgb"], 245)
        RoundedDialog.edge = QColor(*pal["li_rgb"], 80)
        for tile in getattr(self, "tiles", {}).values():
            tile.update()
        self.bg_bottom = pal["bg_bottom"]
        self.bg_glow = pal["bg_glow"]
        self.title_glow.setColor(QColor(*pal["title_glow"], 210))
        self.lbl_title.setText(f'<span style="font-size:36px;">{BRAND_NAME}</span>')
        QApplication.instance().setStyleSheet(build_qss(PIXEL_FONT, pal))
        self.update()

    def set_theme(self, hex_color: str, style: str):
        """Aplica y guarda el tema elegido."""
        self.cfg["theme"] = QColor(hex_color).name()
        self.cfg["theme_style"] = style
        save_config(self.cfg)
        self.apply_theme(self.cfg["theme"], style)

    def _open_theme(self):
        dlg = ThemeDialog(self)
        dlg.exec()
        dlg.deleteLater()

    # ------------------------------------------------------------ avatar
    def _update_avatar(self):
        threading.Thread(target=self._avatar_worker, daemon=True).start()

    def _avatar_worker(self):
        """Busca la skin: la de la cuenta Microsoft si hay sesión online, si no la de Steve."""
        try:
            acc = self.cfg.get("account")
            if acc and acc.get("skin_url"):
                path = CACHE_DIR / "skins" / f"{slugify(acc.get('id', 'cuenta'))}.png"
                download_small(acc["skin_url"], path, host="textures.minecraft.net")
            else:
                path = default_skin()
            self.bus.avatar.emit(str(path))
        except Exception:
            self.bus.avatar.emit("")

    def _set_avatar(self, path: str):
        pix = head_pixmap(path, 60, radius=16) if path else None
        if pix is None:
            pix = silhouette_pixmap(60)
        self.btn_avatar.setIcon(QIcon(pix))
        acc = self.cfg.get("account")
        if acc:
            self.btn_avatar.setToolTip(f"Cuenta · {acc['name']}")
        else:
            self.btn_avatar.setToolTip("Cuenta · inicia sesión con Microsoft")

    # ------------------------------------------------------------ diálogos
    def _open_account(self):
        dlg = AccountDialog(self)
        dlg.exec()
        dlg.deleteLater()

    def _open_logs(self):
        if self.logs_dialog is None:
            self.logs_dialog = LogsDialog(self)
        self.logs_dialog.show()
        self.logs_dialog.raise_()
        self.logs_dialog.activateWindow()

    def _open_ram(self):
        iid = self.current
        if not iid:
            show_message(self, "Memoria RAM", "Elige una instancia primero.")
            return
        entry = self.catalog[iid]
        mb = self.cfg["ram"].get(iid, entry.get("ram_mb", DEFAULT_RAM_MB))
        dlg = RamDialog(self, entry["name"], mb)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.cfg["ram"][iid] = dlg.megabytes()
            save_config(self.cfg)
        dlg.deleteLater()

    # --------------------------------------------------------- cuenta Microsoft
    def _client_id(self) -> str:
        return DEFAULT_CLIENT_ID or self.cfg.get("client_id", "")

    def _ask_client_id(self) -> str:
        text, ok = QInputDialog.getText(
            self, "Client ID de Azure", "Pega el Application (client) ID de tu app de Azure:",
            text=self.cfg.get("client_id", ""))
        if ok and text.strip():
            self.cfg["client_id"] = text.strip()
            save_config(self.cfg)
        return self.cfg.get("client_id", "")

    def _upload_skin(self, path: str, variant: str, name: str = ""):
        """Sube una skin PNG a la cuenta del jugador (API oficial de Minecraft)."""
        if self.busy:
            return
        img = QImage(path)
        if img.isNull() or (img.width(), img.height()) not in ((64, 64), (64, 32)):
            show_message(self, "Skin no válida", "La skin debe ser un PNG de 64×64 o 64×32 píxeles.")
            return
        try:
            png = Path(path).read_bytes()
        except OSError as e:
            show_message(self, "No se pudo leer el archivo", str(e))
            return
        self._apply_busy(True)
        self.bus.status.emit("Subiendo tu skin…")
        threading.Thread(target=self._skin_worker, args=(png, variant, name or Path(path).stem), daemon=True).start()

    def _skin_worker(self, png: bytes, variant: str, name: str):
        bus = self.bus
        try:
            token = self._refresh_account()["access_token"]
            body, ctype = skin_multipart(variant, png)
            profile = mc_api("POST", "/minecraft/profile/skins", token, body, ctype, timeout=60)
            url = pick_skin_url(profile)
            if url:
                self.cfg["account"]["skin_url"] = url
                save_config(self.cfg)
            lib_add(self.cfg["account"]["id"], png, name, variant)        # queda en tu biblioteca
            bus.account.emit()                       # recarga el avatar
            bus.status.emit("Skin actualizada")
        except Exception as e:
            bus.error.emit("No se pudo subir la skin", f"{type(e).__name__}: {e}")
            bus.status.emit("Error al subir la skin")
        finally:
            bus.busy.emit(False)

    def _logout(self):
        self.cfg["account"] = None
        save_config(self.cfg)
        self.bus.account.emit()
        self.bus.status.emit("Sesión cerrada")

    def _login_microsoft(self):
        if self.busy:
            return
        client_id = self._client_id() or self._ask_client_id()
        if not client_id:
            return
        self._apply_busy(True)
        self.bus.status.emit("Abriendo el navegador para iniciar sesión…")
        threading.Thread(target=self._login_worker, args=(client_id,), daemon=True).start()

    def _login_worker(self, client_id: str):
        bus = self.bus
        try:
            login_url, state, verifier = mll.microsoft_account.get_secure_login_data(client_id, REDIRECT_URI)
            if "prompt=" not in login_url:     # que Microsoft deje elegir otra cuenta en vez de reusar la del navegador
                login_url += ("&" if "?" in login_url else "?") + "prompt=select_account"

            captured: dict = {}

            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    if "code=" in self.path or "error=" in self.path:
                        captured["url"] = f"{REDIRECT_URI}{self.path}"
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(
                        "<html><body style='font-family:sans-serif;text-align:center;margin-top:15vh;"
                        "background:#0e0818;color:#f3e8ff'>"
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
            bus.status.emit("Verificando cuenta con Xbox y Minecraft…")
            data = mll.microsoft_account.complete_login(client_id, None, REDIRECT_URI, auth_code, verifier)

            self.cfg["account"] = {
                "id": data["id"],
                "name": data["name"],
                "access_token": data["access_token"],
                "refresh_token": data["refresh_token"],
                "skin_url": pick_skin_url(data),
            }
            save_config(self.cfg)
            bus.account.emit()
            bus.status.emit(f"Sesión iniciada como {data['name']}")
        except Exception as e:
            bus.error.emit("No se pudo iniciar sesión", f"{type(e).__name__}: {e}")
            bus.status.emit("Error al iniciar sesión")
        finally:
            bus.busy.emit(False)

    def _refresh_account(self) -> dict | None:
        """Renueva el token de la cuenta de Microsoft guardada."""
        acc = self.cfg.get("account")
        if not acc:
            raise RuntimeError("Inicia sesión con tu cuenta de Microsoft (toca tu avatar) para jugar.")
        data = mll.microsoft_account.complete_refresh(
            self._client_id(), None, REDIRECT_URI, acc["refresh_token"]
        )
        acc = {
            "id": data["id"],
            "name": data["name"],
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "skin_url": pick_skin_url(data) or acc.get("skin_url", ""),
        }
        self.cfg["account"] = acc
        save_config(self.cfg)
        return acc

    # --------------------------------------------------------------- catálogo
    def _load_cached_manifest(self):
        try:
            self.remote = parse_manifest(json.loads(MANIFEST_CACHE.read_text(encoding="utf-8")))
        except Exception:
            self.remote = []

    def _fetch_catalog(self):
        if self.busy:
            return
        self._apply_busy(True)
        self.bus.status.emit("Buscando instancias…")
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self):
        bus = self.bus
        try:
            data = fetch_json(MANIFEST_URL)
            entries = parse_manifest(data)
            APP_DIR.mkdir(parents=True, exist_ok=True)
            MANIFEST_CACHE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            for e in entries:                       # iconos de las instancias (opcionales)
                if e["icon_url"]:
                    try:
                        download_small(e["icon_url"], icon_path(e["id"]))
                    except Exception:
                        pass
            self.remote = entries
            bus.catalog.emit("")
            bus.status.emit(f"{len(entries)} instancia(s) disponible(s)" if entries
                            else "El catálogo está vacío")
        except Exception as e:
            bus.status.emit(f"No se pudo leer el catálogo ({type(e).__name__}). Se usa la lista guardada.")
        finally:
            bus.busy.emit(False)

    def _needs_install(self, iid: str) -> bool:
        installed = self.cfg["installed"].get(iid)
        entry = self.catalog[iid]
        if installed is None:
            return True
        return not entry.get("local_only") and installed["version"] != entry["version"]

    def _tooltip(self, iid: str) -> str:
        name = self.catalog[iid]["name"]
        if self.cfg["installed"].get(iid) is None:
            return f"{name}\nSe descargará al jugar"
        if self._needs_install(iid):
            return f"{name}\nActualización disponible"
        return name

    def _make_tile(self, iid: str) -> QPushButton:
        entry = self.catalog[iid]
        tile = TileButton()
        tile.setObjectName("tile")
        tile.setCheckable(True)
        tile.setFixedSize(64, 64)
        tile.setCursor(Qt.CursorShape.PointingHandCursor)
        tile.setToolTip(self._tooltip(iid))
        tile.set_progress(self._base_progress(iid))      # gris mientras no esté instalada

        path = icon_path(iid)
        pix = QPixmap(str(path)) if path.exists() else QPixmap()
        if not pix.isNull():
            tile.setIcon(QIcon(rounded_pixmap(pix, 60, 16)))
            tile.setIconSize(QSize(60, 60))
        else:
            tile.setText(entry["name"][:1].upper() or "?")     # sin logo: inicial de la instancia
        tile.clicked.connect(lambda _checked=False, i=iid: self._select(i))
        return tile

    def _rebuild_catalog(self, select: str = ""):
        catalog = {e["id"]: e for e in self.remote}
        # Instancias ya instaladas que ya no están en el catálogo (o sin conexión): se pueden jugar igual
        for iid, inst in self.cfg["installed"].items():
            catalog.setdefault(iid, {
                "id": iid, "name": inst["name"], "summary": inst.get("summary", ""),
                "version": inst["version"], "local_only": True,
            })
        self.catalog = catalog
        self.ids = sorted(catalog, key=lambda i: catalog[i]["name"].lower())

        target = select or self.cfg.get("last_instance")
        self.current = target if target in self.ids else (self.ids[0] if self.ids else None)
        if self.current:
            self.cfg["last_instance"] = self.current

        # Se vuelven a crear los cuadrados
        while self.tiles_lay.count():
            item = self.tiles_lay.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.tiles = {}
        for iid in self.ids:
            tile = self._make_tile(iid)
            self.tiles[iid] = tile
            self.tiles_lay.addWidget(tile, 0, Qt.AlignmentFlag.AlignHCenter)
        self.tiles_lay.addStretch(1)
        self._mark_selected()

    def _mark_selected(self):
        for iid, tile in self.tiles.items():
            tile.setChecked(iid == self.current)
        self._update_play_label()

    def _update_play_label(self):
        """El botón dice «Instalar» si la instancia elegida aún no está instalada."""
        missing = bool(self.current) and self.cfg["installed"].get(self.current) is None
        self.btn_play.setText("Instalar" if missing else "Jugar")

    def _select(self, iid: str):
        if not self.busy:
            self.current = iid
            self.cfg["last_instance"] = iid
        self._mark_selected()

    def _uninstall(self):
        iid = self.current
        if not iid or iid not in self.cfg["installed"]:
            self.bus.status.emit("Esa instancia no está instalada")
            return
        name = self.catalog[iid]["name"]
        if not confirm(self, "Desinstalar instancia",
                       f"¿Desinstalar «{name}»?\n\nSe borrarán también sus mods, mundos y configuración.",
                       yes="Desinstalar", no="Cancelar"):
            return
        game_dir = (INSTANCES_DIR / iid).resolve()
        if INSTANCES_DIR.resolve() in game_dir.parents:   # solo borra dentro de instances/
            shutil.rmtree(game_dir, ignore_errors=True)
        del self.cfg["installed"][iid]
        save_config(self.cfg)
        self._rebuild_catalog(select=iid)
        self.bus.status.emit(f"«{name}» desinstalada")

    def _open_folder(self):
        iid = self.current
        if not iid:
            return
        d = INSTANCES_DIR / iid
        d.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(d)))

    # ----------------------------------------------------------------- jugar
    def _play(self):
        if self.busy:
            return
        iid = self.current
        if not iid:
            show_message(self, "Sin instancia", "Elige una instancia primero.")
            return
        if not self.cfg.get("account"):
            show_message(self, "Inicia sesión",
                         "Para jugar necesitas iniciar sesión con tu cuenta de Microsoft "
                         "(con Minecraft Java Edition).\n\nToca tu avatar, abajo a la derecha.")
            self._open_account()
            return
        self.cfg["last_instance"] = iid
        save_config(self.cfg)
        self._apply_busy(True)
        worker = self._install_worker if self.cfg["installed"].get(iid) is None else self._launch_worker
        threading.Thread(target=worker, args=(iid,), daemon=True).start()

    def _install_worker(self, iid: str):
        """Solo instala (no abre el juego). Después el botón pasa a «Jugar»."""
        bus = self.bus
        entry = self.catalog[iid]
        try:
            self._install(entry, is_update=False)
            bus.catalog.emit(iid)
            bus.status.emit(f"«{entry['name']}» instalada")
        except Exception as e:
            bus.error.emit("Error al instalar", f"{type(e).__name__}: {e}")
            bus.status.emit("Error")
        finally:
            bus.busy.emit(False)

    def _install(self, entry: dict, is_update: bool) -> dict:
        """Descarga e instala la instancia. Se ejecuta en un hilo de trabajo."""
        iid = entry["id"]
        self.installing = iid
        started = time.time()
        cb = self._make_callback()
        game_dir = INSTANCES_DIR / iid
        tmp = DOWNLOADS_DIR / f"{iid}.mrpack"
        MC_DIR.mkdir(parents=True, exist_ok=True)
        game_dir.mkdir(parents=True, exist_ok=True)
        try:
            cb["setStatus"](f"Descargando «{entry['name']}»…")
            download_file(entry["mrpack_url"], tmp, cb, entry.get("sha256", ""))

            if is_update:
                # Se reemplazan los mods; mundos y ajustes del jugador se conservan
                shutil.rmtree(game_dir / "mods", ignore_errors=True)

            ensure_java(cb)
            cb["setStatus"](f"Instalando «{entry['name']}»…")
            mll.mrpack.install_mrpack(
                str(tmp), str(MC_DIR),
                modpack_directory=str(game_dir),
                callback=cb,
                mrpack_install_options={"optionalFiles": []},
            )
            launch_version = mll.mrpack.get_mrpack_launch_version(str(tmp))
            info = mll.mrpack.get_mrpack_information(str(tmp))
        except Exception:
            self.bus.percent.emit(-1)           # quita el gris del cuadrado
            if not is_update:
                shutil.rmtree(game_dir, ignore_errors=True)
            raise
        finally:
            tmp.unlink(missing_ok=True)

        record = {
            "name": entry["name"],
            "summary": entry.get("summary", ""),
            "version": entry["version"],
            "minecraft_version": info.get("minecraftVersion", "?"),
            "launch_version": launch_version,
        }
        self.cfg["installed"][iid] = record
        save_config(self.cfg)
        self.bus.percent.emit(100)
        self.bus.log.emit(f"[{LAUNCHER_NAME}] Instalación de «{entry['name']}» terminada en {int(time.time() - started)} s")
        return record

    def _launch_worker(self, iid: str):
        bus = self.bus
        entry = self.catalog[iid]
        game_dir = INSTANCES_DIR / iid
        try:
            record = self.cfg["installed"].get(iid)
            if self._needs_install(iid):
                record = self._install(entry, is_update=record is not None)
                bus.catalog.emit(iid)

            # Cuenta de Microsoft (renovando el token)
            try:
                account = self._refresh_account()
            except Exception as e:
                raise RuntimeError(
                    f"No se pudo renovar tu sesión de Microsoft ({type(e).__name__}). "
                    "Toca tu avatar, cierra sesión e inicia de nuevo."
                ) from e
            username, player_uuid, token = account["name"], account["id"], account["access_token"]

            ram = int(self.cfg["ram"].get(iid, entry.get("ram_mb", DEFAULT_RAM_MB)))
            options = {
                "username": username,
                "uuid": player_uuid,
                "token": token,
                "gameDirectory": str(game_dir),
                "launcherName": LAUNCHER_NAME,
                "launcherVersion": LAUNCHER_VERSION,
                "jvmArguments": [f"-Xmx{ram}M", "-Xms512M"],
            }
            cmd = mll.command.get_minecraft_command(record["launch_version"], str(MC_DIR), options)

            bus.status.emit(f"Iniciando «{entry['name']}»…")
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            no_window = 0x08000000 if sys.platform.startswith("win") else 0   # sin ventana de consola
            self.game_running = True
            proc = subprocess.Popen(
                cmd, cwd=str(game_dir), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=no_window)
            with open(LOGS_DIR / "latest.log", "w", encoding="utf-8") as fh:
                for line in proc.stdout:
                    line = line.rstrip("\r\n")
                    fh.write(line + "\n")
                    bus.log.emit(line)
            proc.wait()
            bus.status.emit("Minecraft se cerró")
        except Exception as e:
            bus.error.emit("Error al iniciar", f"{type(e).__name__}: {e}")
            bus.status.emit("Error")
        finally:
            self.game_running = False
            bus.busy.emit(False)


PIXEL_FONT = False


def run_pending_update() -> bool:
    """Antes de abrir el launcher: si hay una versión nueva, se descarga el instalador y se ejecuta
    (obligatorio). El instalador reemplaza el programa y lo vuelve a abrir. Devuelve True si el
    launcher debe cerrarse para que el instalador pueda trabajar."""
    if not installed_with_installer():
        return False                       # solo se actualiza lo instalado con el instalador
    try:
        info = parse_update(fetch_json(UPDATE_URL, timeout=6))
    except Exception:
        return False                       # sin internet: se abre la versión actual
    if (not info or not info["installer_url"]
            or parse_version(info["version"]) <= parse_version(LAUNCHER_VERSION)):
        return False

    theme = QColor(load_config().get("theme", DEFAULT_THEME))
    QApplication.instance().setStyleSheet(
        build_qss(PIXEL_FONT, make_palette(theme.name() if theme.isValid() else DEFAULT_THEME)))

    bus = Bus()
    dlg = UpdateDialog(None, info["version"])
    result = {"error": ""}
    setup = Path(tempfile.gettempdir()) / "TOMATE77K-setup.exe"
    state = {"max": 1}

    def set_max(m):
        state["max"] = max(int(m), 1)

    def set_progress(v):
        bus.upd_progress.emit(min(100, int(int(v) * 100 / state["max"])))

    def work():
        try:
            download_file(info["installer_url"], setup,
                          {"setMax": set_max, "setProgress": set_progress}, info["installer_sha256"])
            if setup.stat().st_size < 1_000_000:
                raise RuntimeError("El archivo descargado no parece un instalador válido.")
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {e}"
        bus.upd_done.emit(result["error"])

    bus.upd_progress.connect(dlg.bar.setValue)
    bus.upd_done.connect(lambda _err: dlg.done(0))
    threading.Thread(target=work, daemon=True).start()
    dlg.exec()

    if result["error"]:
        show_message(None, "No se pudo actualizar",
                     f"{result['error']}\n\nSe abrirá la versión actual.")
        return False
    flags = 0x00000008 | 0x00000200 if sys.platform.startswith("win") else 0
    subprocess.Popen([str(setup), "/SILENT", "/SUPPRESSMSGBOXES", "/NOCANCEL", "/CLOSEAPPLICATIONS"],
                     close_fds=True, creationflags=flags)
    return True


def main():
    global PIXEL_FONT
    migrate_legacy_dir()
    app = QApplication(sys.argv)
    app.setApplicationName(LAUNCHER_NAME)
    family, pixel = load_fonts()
    if family:
        app.setFont(QFont(family, 11))
    PIXEL_FONT = pixel
    if run_pending_update():
        sys.exit(0)                      # el instalador reemplaza el programa y lo reabre
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
