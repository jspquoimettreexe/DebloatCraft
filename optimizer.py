"""DebloatCraft: desktop utility for transparent, user-selected PC maintenance."""

from __future__ import annotations

import ctypes
import json
import os
import platform
import subprocess
import sys
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import colorchooser, messagebox, ttk
from typing import Any


APP_NAME = "DebloatCraft"
IS_LINUX = sys.platform.startswith("linux")
BG = "#0b1020"
PANEL = "#111a31"
PANEL_ALT = "#17213b"
TEXT = "#f3f5ff"
MUTED = "#a4aec9"
BLUE = "#4ca5ff"
PURPLE = "#9564ff"
GREEN = "#65e6be"
ORANGE = "#ffbd68"
PALETTE = ["#4ca5ff", "#9564ff", "#ff5fa2", "#ff9b54", "#65e6be", "#f4f6ff"]
THEMES = {
    "Noir profond": {"bg": "#0b1020", "panel": "#111a31", "panel_alt": "#17213b", "text": "#f3f5ff", "muted": "#a4aec9"},
    "Gris doux": {"bg": "#171a22", "panel": "#222631", "panel_alt": "#303642", "text": "#f1f2f5", "muted": "#b3b8c5"},
    "Blanc lumineux": {"bg": "#edf1f8", "panel": "#ffffff", "panel_alt": "#e2e8f2", "text": "#1a2030", "muted": "#59647a"},
}


def set_theme_palette(mode: str, contrast: str = "Équilibré") -> str:
    global BG, PANEL, PANEL_ALT, TEXT, MUTED
    selected = mode if mode in THEMES else "Noir profond"
    palette = THEMES[selected]
    BG, PANEL, PANEL_ALT = palette["bg"], palette["panel"], palette["panel_alt"]
    TEXT, MUTED = palette["text"], palette["muted"]
    if contrast == "Discret":
        TEXT, MUTED = ("#d0d3dc", "#9399a8") if selected != "Blanc lumineux" else ("#3d4658", "#788196")
    elif contrast == "Très contrasté":
        TEXT, MUTED = ("#ffffff", "#d2d8e8") if selected != "Blanc lumineux" else ("#080d18", "#35425a")
    return selected

REGISTRY_SETTINGS = {
    "capture": {
        "label": "Désactiver Game DVR et la capture en arrière-plan",
        "description": "À choisir si tu n'utilises pas les captures Xbox. Réversible.",
        "values": [
            ("HKCU", r"System\GameConfigStore", "GameDVR_Enabled", 0, "DWORD"),
            ("HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR", "AppCaptureEnabled", 0, "DWORD"),
        ],
    },
    "background": {
        "label": "Limiter les applications Windows en arrière-plan",
        "description": "Peut réduire certaines notifications d'applications. Réversible.",
        "values": [
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications", "GlobalUserDisabled", 1, "DWORD"),
        ],
    },
    "visuals": {
        "label": "Privilégier les performances visuelles",
        "description": "Réduit certains effets visuels du compte Windows courant.",
        "values": [
            ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects", "VisualFXSetting", 2, "DWORD"),
        ],
    },
    "games": {
        "label": "Priorité multimédia pour les jeux",
        "description": "Règle les priorités Windows documentées pour la tâche Games.",
        "values": [
            ("HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "Scheduling Category", "High", "SZ"),
            ("HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games", "SFIO Priority", "High", "SZ"),
        ],
    },
}


def config_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_NAME / "settings.json"


def load_config() -> dict[str, Any]:
    try:
        with config_path().open("r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(config: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def is_admin() -> bool:
    if IS_LINUX:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_powershell_json() -> dict[str, Any]:
    script = r"""
$cpu = (Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)
$gpu = (Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name }) -join ' / '
$os = Get-CimInstance Win32_OperatingSystem
$disks = @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object {
    [pscustomobject]@{ name=$_.DeviceID; size=[math]::Round($_.Size/1GB,0); free=[math]::Round($_.FreeSpace/1GB,0) }
})
[pscustomobject]@{
    cpu=$cpu; gpu=$gpu; ram=[math]::Round($os.TotalVisibleMemorySize/1MB,0)
    windows=$os.Caption; version=$os.Version; disks=$disks
} | ConvertTo-Json -Compress -Depth 3
"""
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    data = json.loads(completed.stdout.strip())
    return data if isinstance(data, dict) else {}


def run_linux_hardware_json() -> dict[str, Any]:
    cpu = platform.processor().strip() or "Non détecté"
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace").splitlines():
            key, separator, value = line.partition(":")
            value = value.strip()
            if separator and key.strip().lower() in ("model name", "hardware") and value:
                cpu = value
                break
            if (separator and key.strip().lower() == "processor" and value
                    and not value.isdigit() and cpu == "Non détecté"):
                cpu = value
    except OSError:
        pass

    ram = None
    try:
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            if line.startswith("MemTotal:"):
                ram = round(int(line.split()[1]) / 1024 / 1024)
                break
    except (OSError, ValueError, IndexError):
        pass

    gpu = "Non détectée"
    if shutil.which("lspci"):
        try:
            result = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5, check=False)
            devices = [line.split(": ", 1)[-1] for line in result.stdout.splitlines()
                       if "vga compatible controller" in line.lower()
                       or "3d controller" in line.lower()
                       or "display controller" in line.lower()]
            if devices:
                gpu = " / ".join(devices)
        except (OSError, subprocess.SubprocessError):
            pass

    try:
        release = platform.freedesktop_os_release()
        system = f"{release.get('PRETTY_NAME', 'Linux')} · {platform.release()}"
    except (AttributeError, OSError):
        system = f"Linux · {platform.release()}"

    disks = []
    checked_paths: set[str] = set()
    for path in (Path("/"), Path.home()):
        try:
            resolved = str(path.resolve())
            if resolved in checked_paths:
                continue
            checked_paths.add(resolved)
            usage = shutil.disk_usage(path)
            disks.append({"name": resolved, "size": round(usage.total / 1024**3),
                          "free": round(usage.free / 1024**3)})
        except OSError:
            continue

    return {"cpu": cpu, "gpu": gpu, "ram": ram, "windows": system, "version": "", "disks": disks}


def registry_root(root_name: str) -> Any:
    import winreg

    return winreg.HKEY_CURRENT_USER if root_name == "HKCU" else winreg.HKEY_LOCAL_MACHINE


def read_registry_value(root_name: str, key_path: str, value_name: str) -> tuple[bool, Any, int | None]:
    import winreg

    try:
        with winreg.OpenKey(registry_root(root_name), key_path, 0, winreg.KEY_QUERY_VALUE) as key:
            value, value_type = winreg.QueryValueEx(key, value_name)
        return True, value, value_type
    except FileNotFoundError:
        return False, None, None


def write_registry_value(root_name: str, key_path: str, value_name: str, value: Any, value_type: int) -> None:
    import winreg

    with winreg.CreateKeyEx(registry_root(root_name), key_path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, value_name, 0, value_type, value)


def restore_registry_value(root_name: str, key_path: str, value_name: str, existed: bool, value: Any, value_type: int | None) -> None:
    import winreg

    try:
        with winreg.OpenKey(registry_root(root_name), key_path, 0, winreg.KEY_SET_VALUE) as key:
            if existed and value_type is not None:
                winreg.SetValueEx(key, value_name, 0, value_type, value)
            else:
                try:
                    winreg.DeleteValue(key, value_name)
                except FileNotFoundError:
                    pass
    except FileNotFoundError:
        if existed and value_type is not None:
            write_registry_value(root_name, key_path, value_name, value, value_type)


def installed_programs() -> list[dict[str, str]]:
    if os.name != "nt":
        commands = []
        if shutil.which("dpkg-query"):
            commands.append(["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\n"])
        elif shutil.which("rpm"):
            commands.append(["rpm", "-qa", "--qf", "%{NAME}\t%{VERSION}-%{RELEASE}\n"])
        elif shutil.which("pacman"):
            commands.append(["pacman", "-Q"])
        programs: dict[str, dict[str, str]] = {}
        for command in commands:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    name, separator, version = line.partition("\t")
                    if not separator:
                        name, separator, version = line.partition(" ")
                    if separator and name:
                        programs[name.casefold()] = {"name": name, "version": version, "publisher": ""}
                break
        if shutil.which("flatpak"):
            result = subprocess.run(["flatpak", "list", "--app", "--columns=application,version"],
                                    capture_output=True, text=True, timeout=30, check=False)
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    name, _, version = line.partition("\t")
                    if name:
                        programs.setdefault(name.casefold(), {"name": name, "version": version, "publisher": "Flatpak"})
        return sorted(programs.values(), key=lambda item: item["name"].casefold())

    import winreg

    locations = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    programs: dict[str, dict[str, str]] = {}
    for root, path in locations:
        try:
            with winreg.OpenKey(root, path) as parent:
                for index in range(winreg.QueryInfoKey(parent)[0]):
                    try:
                        child_name = winreg.EnumKey(parent, index)
                        with winreg.OpenKey(parent, child_name) as child:
                            name = str(winreg.QueryValueEx(child, "DisplayName")[0]).strip()
                            if not name:
                                continue
                            try:
                                version = str(winreg.QueryValueEx(child, "DisplayVersion")[0])
                            except OSError:
                                version = ""
                            try:
                                publisher = str(winreg.QueryValueEx(child, "Publisher")[0])
                            except OSError:
                                publisher = ""
                            programs.setdefault(name.casefold(), {
                                "name": name, "version": version, "publisher": publisher,
                            })
                    except OSError:
                        continue
        except OSError:
            continue
    return sorted(programs.values(), key=lambda item: item["name"].casefold())


def directory_size(path: Path) -> int:
    size = 0
    try:
        for root, dirs, files in os.walk(path, followlinks=False):
            dirs[:] = [name for name in dirs if not (Path(root) / name).is_symlink()]
            for name in files:
                item = Path(root) / name
                try:
                    if not item.is_symlink():
                        size += item.stat().st_size
                except OSError:
                    continue
    except OSError:
        pass
    return size


def format_bytes(size: int) -> str:
    units = ("o", "Ko", "Mo", "Go", "To")
    amount = float(size)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{size} o"


def accent_text_color(shade: str) -> str:
    channels = [int(shade[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    luminance = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
    return "#11152b" if luminance > 0.179 else "#ffffff"


class DebloatCraftApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("DebloatCraft | Réglages PC transparents")
        self.geometry("1180x790")
        self.minsize(980, 680)
        self.configure(bg=BG)
        self.config_data = load_config()
        self.config_data["color_mode"] = set_theme_palette(
            self.config_data.get("color_mode", "Noir profond"),
            self.config_data.get("visual_preference", {}).get("contrast", "Équilibré"),
        )
        self.accent = self.config_data.get("accent", BLUE)
        if not isinstance(self.accent, str) or len(self.accent) != 7 or not self.accent.startswith("#"):
            self.accent = BLUE
        self.current_page = "Vue d'ensemble"
        self.hardware: dict[str, Any] | None = None
        self.vars: dict[str, tk.BooleanVar] = {}
        self.clean_paths: dict[str, Path] = {}
        self.profile_box: tk.Listbox | None = None
        self.profile_name: tk.StringVar | None = None
        self.profile_color: str = self.accent
        self.program_tree: ttk.Treeview | None = None
        self.disk_tree: ttk.Treeview | None = None
        self.recommendation_label: tk.Label | None = None
        self._setup_styles()
        self._build_shell()
        self.show_page("Vue d'ensemble")

    def _setup_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, foreground=TEXT, fieldbackground=PANEL,
                        rowheight=32, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=PANEL_ALT, foreground=TEXT,
                        relief="flat", font=("Segoe UI Semibold", 9))
        style.map("Treeview", background=[("selected", "#303d66")], foreground=[("selected", TEXT)])
        style.configure("TScrollbar", background=PANEL_ALT, troughcolor=BG, borderwidth=0)

    def _build_shell(self) -> None:
        self.sidebar = tk.Frame(self, bg="#0e1529", width=224)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg="#0e1529")
        brand.pack(fill="x", padx=22, pady=(24, 26))
        tk.Label(brand, text="DC", fg=accent_text_color(self.accent), bg=self.accent, font=("Segoe UI Black", 15),
                 width=3, height=1).pack(side="left", padx=(0, 10))
        title_box = tk.Frame(brand, bg="#0e1529")
        title_box.pack(side="left")
        tk.Label(title_box, text="DEBLOATCRAFT", fg=TEXT, bg="#0e1529",
                 font=("Segoe UI Semibold", 11)).pack(anchor="w")
        tk.Label(title_box, text="FREE PC TOOL", fg=MUTED, bg="#0e1529",
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 0))

        tk.Label(self.sidebar, text="ESPACE DE TRAVAIL", fg="#707c9c", bg="#0e1529",
                 font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=22, pady=(0, 10))
        self.nav_buttons: dict[str, tk.Button] = {}
        pages = [
            ("Vue d'ensemble", "⌂"), ("Optimisation Windows" if os.name == "nt" else "Réglages Linux", "◈"),
            ("Stockage", "▤"), ("Applications", "▦"),
            ("Apparence Windows" if os.name == "nt" else "Apparence de l'outil", "◉"),
            ("Profils de jeux", "◇"), ("Quiz couleurs", "✳"),
        ]
        for name, icon in pages:
            button = tk.Button(
                self.sidebar, text=f"  {icon}    {name}", anchor="w", bd=0,
                padx=14, pady=11, bg="#0e1529", fg="#aab4cf",
                activebackground="#202a46", activeforeground=TEXT,
                font=("Segoe UI", 10), command=lambda page=name: self.show_page(page),
            )
            button.pack(fill="x", padx=12, pady=2)
            self.nav_buttons[name] = button

        tk.Frame(self.sidebar, bg="#26304b", height=1).pack(fill="x", padx=20, pady=18)
        tk.Label(self.sidebar, text="SYSTÈME", fg="#707c9c", bg="#0e1529",
                 font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=22, pady=(0, 9))
        self.admin_label = tk.Label(
            self.sidebar,
            text=("●  Administrateur" if is_admin() else "●  Mode lecture seule") if os.name == "nt" else "●  Mode lecture seule",
            fg=GREEN if is_admin() else ORANGE, bg="#0e1529", font=("Segoe UI", 9),
        )
        self.admin_label.pack(anchor="w", padx=22)
        tk.Label(self.sidebar, text="GRATUIT · SANS COMPTE", fg="#727d9b", bg="#0e1529",
                 font=("Segoe UI", 8)).pack(side="bottom", anchor="w", padx=22, pady=20)

        self.workspace = tk.Frame(self, bg=BG)
        self.workspace.pack(side="left", fill="both", expand=True)
        self.header = tk.Canvas(self.workspace, height=78, bg=BG, highlightthickness=0)
        self.header.pack(fill="x")
        self.header.bind("<Configure>", self._draw_gradient)
        self.page_content = tk.Frame(self.workspace, bg=BG)
        self.page_content.pack(fill="both", expand=True)
        self.status_var = tk.StringVar(value="Prêt · aucun réglage appliqué")
        status_bar = tk.Frame(self.workspace, bg="#0e1529", height=34)
        status_bar.pack(side="bottom", fill="x")
        tk.Label(status_bar, textvariable=self.status_var, bg="#0e1529", fg=MUTED,
                 font=("Segoe UI", 9), anchor="w").pack(fill="both", padx=18)

    def _draw_gradient(self, _event: Any = None) -> None:
        self.header.delete("all")
        width = max(self.header.winfo_width(), 2)
        height = max(self.header.winfo_height(), 2)
        start = (76, 165, 255)
        end = (149, 100, 255)
        for x in range(width):
            ratio = x / width
            rgb = tuple(round(start[i] * (1 - ratio) + end[i] * ratio) for i in range(3))
            self.header.create_line(x, 0, x, height, fill="#%02x%02x%02x" % rgb)
        self.header.create_text(24, 27, text="CONTROL CENTER", anchor="w", fill="white",
                                font=("Segoe UI Semibold", 17))
        self.header.create_text(25, 55, text="SCAN LOCAL  ·  RÉGLAGES AU CHOIX  ·  GRATUIT",
                                anchor="w", fill="#e6eaff", font=("Segoe UI", 8))
        self.header.create_text(width - 22, height / 2, text="WINDOWS 10 / 11" if os.name == "nt" else "LINUX",
                                anchor="e", fill="white", font=("Segoe UI Semibold", 9))

    def show_page(self, name: str) -> None:
        self.current_page = name
        for page, button in self.nav_buttons.items():
            button.configure(bg="#202a46" if page == name else "#0e1529",
                             fg=TEXT if page == name else "#aab4cf")
        for child in self.page_content.winfo_children():
            child.destroy()
        self.page_content.grid_columnconfigure(0, weight=1)
        if name == "Vue d'ensemble":
            self._dashboard()
        elif name in ("Optimisation Windows", "Réglages Linux"):
            self._optimization_page()
        elif name == "Stockage":
            self._storage_page()
        elif name == "Applications":
            self._applications_page()
        elif name in ("Apparence Windows", "Apparence de l'outil"):
            self._appearance_page()
        elif name == "Profils de jeux":
            self._profiles_page()
        elif name == "Quiz couleurs":
            self._quiz_page()

    def _page_heading(self, eyebrow: str, title: str, subtitle: str = "") -> tk.Frame:
        heading = tk.Frame(self.page_content, bg=BG)
        heading.pack(fill="x", padx=30, pady=(24, 18))
        tk.Label(heading, text=eyebrow.upper(), fg=self.accent, bg=BG,
                 font=("Segoe UI Semibold", 9)).pack(anchor="w")
        tk.Label(heading, text=title, fg=TEXT, bg=BG,
                 font=("Segoe UI Semibold", 24)).pack(anchor="w", pady=(3, 0))
        if subtitle:
            tk.Label(heading, text=subtitle, fg=MUTED, bg=BG,
                     font=("Segoe UI", 10)).pack(anchor="w", pady=(5, 0))
        return heading

    def _card(self, parent: tk.Widget, title: str, subtitle: str = "") -> tk.Frame:
        card = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground="#252f4c")
        if title or subtitle:
            heading = tk.Frame(card, bg=PANEL)
            heading.pack(fill="x", padx=18, pady=(15, 11))
            tk.Label(heading, text=title, fg=TEXT, bg=PANEL,
                     font=("Segoe UI Semibold", 11)).pack(anchor="w")
            if subtitle:
                tk.Label(heading, text=subtitle, fg=MUTED, bg=PANEL,
                         font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))
        return card

    def _button(self, parent: tk.Widget, text: str, command: Any, primary: bool = True) -> tk.Button:
        return tk.Button(parent, text=text, command=command, bd=0, padx=15, pady=9,
                         bg=self.accent if primary else PANEL_ALT,
                         fg=accent_text_color(self.accent) if primary else TEXT,
                         activebackground=PURPLE if primary else "#283453",
                         activeforeground="white", font=("Segoe UI Semibold", 9), cursor="hand2")

    def _dashboard(self) -> None:
        system_label = "Windows" if os.name == "nt" else "Système Linux"
        self._page_heading("Diagnostic · 01", "Vue d'ensemble",
                           "Analyse locale en lecture seule. Rien ne sera modifié par le scan.")
        actions = tk.Frame(self.page_content, bg=BG)
        actions.pack(fill="x", padx=30, pady=(0, 14))
        self._button(actions, "Scanner les composants", self.scan_hardware).pack(side="left")
        tk.Label(actions, text=f"CPU · GPU · mémoire · {system_label} · disques", fg=MUTED,
                 bg=BG, font=("Segoe UI", 9)).pack(side="left", padx=14)

        grid = tk.Frame(self.page_content, bg=BG)
        grid.pack(fill="both", expand=True, padx=30, pady=(0, 18))
        for column in range(2):
            grid.grid_columnconfigure(column, weight=1, uniform="dashboard")
        cards = [
            ("Processeur", "cpu"), ("Carte graphique", "gpu"),
            ("Mémoire vive", "ram"), (system_label, "windows"),
        ]
        self.hardware_labels: dict[str, tk.Label] = {}
        for index, (label, key) in enumerate(cards):
            card = self._card(grid, label)
            card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=(0, 12) if index % 2 == 0 else (0, 0), pady=7)
            value = tk.Label(card, text="À scanner", fg=TEXT, bg=PANEL,
                             font=("Segoe UI Semibold", 13), wraplength=410, justify="left")
            value.pack(anchor="w", padx=18, pady=(0, 17))
            self.hardware_labels[key] = value

        disk_card = self._card(grid, "Stockage local", "Capacité et espace libre des disques détectés")
        disk_card.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=7)
        self.dashboard_disks = tk.Label(disk_card, text="À scanner", fg=MUTED, bg=PANEL,
                                        font=("Segoe UI", 10), justify="left")
        self.dashboard_disks.pack(anchor="w", padx=18, pady=(0, 17))
        if self.hardware is None:
            self.after(350, self.scan_hardware)

    def scan_hardware(self) -> None:
        self.status_var.set("Scan matériel en cours… aucune écriture système")
        self.update_idletasks()
        try:
            self.hardware = run_powershell_json() if os.name == "nt" else run_linux_hardware_json()
            values = {
                "cpu": self.hardware.get("cpu") or "Non détecté",
                "gpu": self.hardware.get("gpu") or "Non détectée",
                "ram": f"{self.hardware.get('ram', '?')} Go",
                "windows": f"{self.hardware.get('windows', 'Windows')} · {self.hardware.get('version', '')}",
            }
            for key, value in values.items():
                label = self.hardware_labels.get(key)
                if label and label.winfo_exists():
                    label.configure(text=value)
            disks = self.hardware.get("disks", [])
            disk_text = "\n".join(
                f"{disk.get('name', '?')}  ·  {disk.get('free', '?')} Go libres / {disk.get('size', '?')} Go"
                for disk in disks
            ) or "Aucun disque fixe détecté"
            if hasattr(self, "dashboard_disks") and self.dashboard_disks.winfo_exists():
                self.dashboard_disks.configure(text=disk_text)
            self._update_recommendations()
            self.status_var.set("Scan terminé · recommandations informatives, aucun changement appliqué")
        except Exception as exc:
            self.status_var.set("Scan impossible")
            messagebox.showerror("Scan matériel", f"Le scan matériel a échoué.\n\n{exc}")

    def _update_recommendations(self) -> None:
        if not self.recommendation_label or not self.recommendation_label.winfo_exists() or not self.hardware:
            return
        suggestions: list[str] = []
        ram = self.hardware.get("ram")
        if isinstance(ram, (int, float)) and ram <= 8:
            advice = "garde le fichier d'échange Windows activé" if os.name == "nt" else "ferme les applications lourdes avant de jouer"
            suggestions.append(f"Mémoire limitée: {advice}.")
        elif isinstance(ram, (int, float)):
            suggestions.append(f"{ram:g} Go de mémoire détectés: évite les tweaks de pagination du noyau, qui n'apportent pas de gain universel.")
        gpu = str(self.hardware.get("gpu", "")).casefold()
        if any(name in gpu for name in ("intel uhd", "intel hd", "iris xe")):
            suggestions.append("Graphique intégré détecté: privilégie le profil d'alimentation recommandé par le fabricant et ajuste résolution/qualité dans le jeu.")
        elif gpu:
            suggestions.append("Vérifie que le jeu utilise le GPU dédié et garde son pilote à jour depuis le fabricant.")
        for disk in self.hardware.get("disks", []):
            size, free = disk.get("size"), disk.get("free")
            if isinstance(size, (int, float)) and size and isinstance(free, (int, float)) and free / size < 0.1:
                suggestions.append(f"Le disque {disk.get('name', '')} a moins de 10 % d'espace libre: libère de l'espace avant les mises à jour de jeux.")
        if not suggestions:
            suggestions.append("Aucun goulot d'étranglement évident n'est déduit de ces seules données. Les réglages proposés restent facultatifs.")
        self.recommendation_label.configure(text="\n\n".join(suggestions))

    def _optimization_page(self) -> None:
        if os.name != "nt":
            self._page_heading("Réglages · 02", "Réglages système",
                               "DebloatCraft ne modifie pas automatiquement les services ou paramètres du système Linux.")
            note = self._card(self.page_content, "Diagnostic sans risque", "Le scan et les conseils matériels restent disponibles sans droits administrateur.")
            note.pack(fill="x", padx=30, pady=(0, 14))
            tk.Label(note, text="Les réglages varient selon la distribution et le matériel. Aucun tweak noyau, service ou réseau n'est appliqué par cet outil.",
                     bg=PANEL, fg=ORANGE, font=("Segoe UI", 9), wraplength=850, justify="left").pack(anchor="w", padx=18, pady=(0, 15))
            return
        self._page_heading("Réglages · 02", "Optimisation Windows",
                           "Choisis les changements un par un. Les valeurs d'origine sont sauvegardées pour restauration.")
        warning = self._card(self.page_content, "Pas de réglage universel", "Le scan aide à comprendre ton PC, mais n'applique rien automatiquement.")
        warning.pack(fill="x", padx=30, pady=(0, 14))
        tk.Label(warning, text="Les tweaks TCP, la désactivation de services et la pagination du noyau sont exclus: leurs effets sont variables et parfois négatifs.",
                 bg=PANEL, fg=ORANGE, font=("Segoe UI", 9), wraplength=850, justify="left").pack(anchor="w", padx=18, pady=(0, 15))

        choices = self._card(self.page_content, "Réglages disponibles")
        choices.pack(fill="x", padx=30, pady=(0, 16))
        self.vars = {}
        for key, item in REGISTRY_SETTINGS.items():
            row = tk.Frame(choices, bg=PANEL)
            row.pack(fill="x", padx=18, pady=(9, 8))
            variable = tk.BooleanVar(value=False)
            self.vars[key] = variable
            tk.Checkbutton(row, variable=variable, text=item["label"], bg=PANEL, fg=TEXT,
                           activebackground=PANEL, activeforeground=TEXT, selectcolor=PANEL_ALT,
                           font=("Segoe UI Semibold", 10)).pack(anchor="w")
            tk.Label(row, text=item["description"], bg=PANEL, fg=MUTED,
                     font=("Segoe UI", 9)).pack(anchor="w", padx=(27, 0), pady=(2, 0))
        actions = tk.Frame(self.page_content, bg=BG)
        actions.pack(fill="x", padx=30)
        self._button(actions, "Appliquer la sélection", self.apply_selected).pack(side="left")
        self._button(actions, "Restaurer les valeurs sauvegardées", self.restore_settings, False).pack(side="left", padx=10)
        if not is_admin():
            tk.Label(self.page_content, text="Certaines actions nécessitent les droits administrateur.",
                     fg=ORANGE, bg=BG, font=("Segoe UI", 9)).pack(anchor="w", padx=32, pady=12)
        recommendation = self._card(self.page_content, "Conseils selon ta configuration")
        recommendation.pack(fill="x", padx=30, pady=(16, 0))
        self.recommendation_label = tk.Label(
            recommendation,
            text="Lance le scan depuis Vue d'ensemble pour afficher des conseils liés au matériel détecté.",
            bg=PANEL, fg=MUTED, font=("Segoe UI", 9), wraplength=850, justify="left",
        )
        self.recommendation_label.pack(anchor="w", padx=18, pady=(0, 15))
        self._update_recommendations()

    def apply_selected(self) -> None:
        selected = [key for key, variable in self.vars.items() if variable.get()]
        if not selected:
            messagebox.showinfo("Aucun choix", "Sélectionne au moins un réglage.")
            return
        if "games" in selected and not is_admin():
            messagebox.showerror("Droits administrateur", "Ce réglage touche une clé machine Windows. Relance l'application comme administrateur.")
            return
        if not messagebox.askyesno("Confirmer les changements", "Les valeurs précédentes seront sauvegardées. Continuer?"):
            return
        try:
            backup = self.config_data.setdefault("registry_backup", {})
            import winreg
            types = {"DWORD": winreg.REG_DWORD, "SZ": winreg.REG_SZ}
            for setting_key in selected:
                for root, key_path, value_name, value, kind in REGISTRY_SETTINGS[setting_key]["values"]:
                    backup_id = f"{root}|{key_path}|{value_name}"
                    if backup_id not in backup:
                        existed, old_value, old_type = read_registry_value(root, key_path, value_name)
                        backup[backup_id] = {
                            "root": root, "path": key_path, "name": value_name,
                            "existed": existed, "value": old_value, "type": old_type,
                        }
                    save_config(self.config_data)
                    write_registry_value(root, key_path, value_name, value, types[kind])
            save_config(self.config_data)
            self.status_var.set(f"Appliqué · {len(selected)} catégorie(s) · restauration disponible")
            messagebox.showinfo("Terminé", "Réglages appliqués. Un redémarrage ou une déconnexion Windows peut être nécessaire.")
        except Exception as exc:
            try:
                save_config(self.config_data)
            except OSError:
                pass
            messagebox.showerror("Application incomplète", f"Une action a échoué; les autres valeurs peuvent déjà être appliquées.\n\n{exc}")

    def restore_settings(self) -> None:
        backup = self.config_data.get("registry_backup", {})
        if not backup:
            messagebox.showinfo("Restauration", "Aucune valeur sauvegardée par DebloatCraft.")
            return
        if any(entry.get("root") == "HKLM" for entry in backup.values()) and not is_admin():
            messagebox.showerror("Droits administrateur", "Certaines valeurs sauvegardées sont machine. Relance l'application comme administrateur pour les restaurer.")
            return
        if not messagebox.askyesno("Restaurer", f"Restaurer {len(backup)} valeur(s) sauvegardée(s)?"):
            return
        errors: list[str] = []
        for entry in list(backup.values()):
            try:
                restore_registry_value(entry["root"], entry["path"], entry["name"],
                                       entry["existed"], entry["value"], entry["type"])
            except Exception as exc:
                errors.append(f"{entry['name']}: {exc}")
        if not errors:
            self.config_data["registry_backup"] = {}
            save_config(self.config_data)
            self.status_var.set("Valeurs d'origine restaurées")
            messagebox.showinfo("Restauration", "Les valeurs sauvegardées ont été restaurées.")
        else:
            messagebox.showwarning("Restauration partielle", "\n".join(errors[:8]))

    def _storage_page(self) -> None:
        self._page_heading("Entretien · 03", "Stockage", "Prévisualise l'espace récupérable avant de supprimer des caches.")
        card = self._card(self.page_content, "Emplacements nettoyables", "Les fichiers ouverts ou verrouillés sont ignorés.")
        card.pack(fill="both", expand=True, padx=30, pady=(0, 14))
        columns = ("location", "size")
        self.disk_tree = ttk.Treeview(card, columns=columns, show="headings", selectmode="extended", height=9)
        self.disk_tree.heading("location", text="EMPLACEMENT")
        self.disk_tree.heading("size", text="TAILLE APPROX.")
        self.disk_tree.column("location", width=650)
        self.disk_tree.column("size", width=140, anchor="e")
        self.disk_tree.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        controls = tk.Frame(card, bg=PANEL)
        controls.pack(fill="x", padx=16, pady=(0, 16))
        self._button(controls, "Analyser", self.scan_storage).pack(side="left")
        self._button(controls, "Nettoyer la sélection", self.clean_storage, False).pack(side="left", padx=10)
        if os.name == "nt":
            self._button(controls, "Vider le cache DNS", self.flush_dns, False).pack(side="left")
        self.scan_storage()

    def scan_storage(self) -> None:
        if not self.disk_tree:
            return
        self.disk_tree.delete(*self.disk_tree.get_children())
        self.clean_paths = {}
        paths: dict[str, Path] = {}
        temp_path = Path(os.environ.get("TEMP", str(Path.home() / "AppData/Local/Temp")))
        if os.name == "nt":
            paths["Temp utilisateur"] = temp_path
        else:
            cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
            for label, relative in (("Miniatures", "thumbnails"), ("Shaders Mesa", "mesa_shader_cache"),
                                    ("Base shaders Mesa", "mesa_shader_cache_db")):
                paths[f"Cache utilisateur · {label}"] = cache / relative
        local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
        epic_saved = local / "EpicGamesLauncher" / "Saved"
        try:
            for candidate in epic_saved.iterdir():
                if candidate.is_dir() and candidate.name.casefold().startswith("webcache"):
                    paths[f"Epic Games · {candidate.name}"] = candidate
        except OSError:
            pass
        for steam_root in self._steam_roots():
            cache = steam_root / "appcache" / "httpcache"
            if cache.is_dir():
                paths[f"Steam · {steam_root}"] = cache
        for label, path in paths.items():
            if path.is_dir():
                size = directory_size(path)
                item_id = self.disk_tree.insert("", "end", values=(label, format_bytes(size)))
                self.clean_paths[item_id] = path
        self.status_var.set(f"Analyse stockage terminée · {len(self.clean_paths)} emplacement(s) trouvé(s)")

    @staticmethod
    def _steam_roots() -> list[Path]:
        if IS_LINUX:
            candidates = [Path.home() / ".steam/steam", Path.home() / ".local/share/Steam"]
            return list({str(path.resolve()): path for path in candidates if path.is_dir()}.values())
        import winreg

        roots: list[Path] = []
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
                roots.append(Path(steam_path))
        except OSError:
            pass
        for env in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
            if env:
                roots.append(Path(env) / "Steam")
        unique: dict[str, Path] = {}
        for root in roots:
            if root.is_dir():
                unique[os.path.normcase(str(root.resolve()))] = root
        return list(unique.values())

    def clean_storage(self) -> None:
        if not self.disk_tree:
            return
        selected = self.disk_tree.selection()
        if not selected:
            messagebox.showinfo("Nettoyage", "Sélectionne les emplacements à nettoyer.")
            return
        if not messagebox.askyesno("Confirmer le nettoyage", "Supprimer le contenu des caches sélectionnés? Les fichiers verrouillés seront ignorés."):
            return
        removed = skipped = 0
        for item_id in selected:
            path = self.clean_paths.get(item_id)
            if not path or not path.is_dir():
                continue
            for child in path.iterdir():
                try:
                    if child.is_symlink() or not child.is_dir():
                        child.unlink()
                    else:
                        shutil.rmtree(child)
                    removed += 1
                except OSError:
                    skipped += 1
        self.scan_storage()
        self.status_var.set(f"Nettoyage terminé · {removed} élément(s), {skipped} ignoré(s)")

    def flush_dns(self) -> None:
        try:
            subprocess.run(["ipconfig.exe", "/flushdns"], check=True, capture_output=True,
                           text=True, timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.status_var.set("Cache DNS vidé")
        except Exception as exc:
            messagebox.showerror("Cache DNS", f"Impossible de vider le cache DNS.\n\n{exc}")

    def _applications_page(self) -> None:
        linux = IS_LINUX
        self._page_heading("Logiciels · 04", "Applications installées",
                           "Inventaire local des paquets système et Flatpak." if linux else "Inventaire local des applications Win32. La désinstallation reste gérée par Windows.")
        card = self._card(self.page_content, "Programmes détectés",
                          "Inventaire en lecture seule; utilise le gestionnaire de ta distribution pour désinstaller." if linux else "Sélectionne une ligne puis ouvre les paramètres d'applications Windows.")
        card.pack(fill="both", expand=True, padx=30, pady=(0, 14))
        columns = ("name", "version", "publisher")
        self.program_tree = ttk.Treeview(card, columns=columns, show="headings", selectmode="browse")
        for column, heading, width in (("name", "APPLICATION", 390), ("version", "VERSION", 130), ("publisher", "ÉDITEUR", 260)):
            self.program_tree.heading(column, text=heading)
            self.program_tree.column(column, width=width)
        self.program_tree.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        bottom = tk.Frame(card, bg=PANEL)
        bottom.pack(fill="x", padx=16, pady=(0, 16))
        self._button(bottom, "Actualiser la liste", self.refresh_programs, False).pack(side="left")
        if not linux:
            self._button(bottom, "Ouvrir la désinstallation Windows", self.open_uninstall_settings).pack(side="left", padx=10)
        tk.Label(bottom, text="Inventaire en lecture seule" if linux else "Aucune suppression silencieuse", fg=GREEN, bg=PANEL,
                 font=("Segoe UI", 9)).pack(side="right", padx=4)
        self.refresh_programs()

    def refresh_programs(self) -> None:
        if not self.program_tree:
            return
        self.program_tree.delete(*self.program_tree.get_children())
        try:
            for program in installed_programs():
                self.program_tree.insert("", "end", values=(program["name"], program["version"], program["publisher"]))
            self.status_var.set(f"Inventaire terminé · {len(self.program_tree.get_children())} application(s)")
        except Exception as exc:
            messagebox.showerror("Applications", f"Impossible de lire la liste des logiciels.\n\n{exc}")

    def open_uninstall_settings(self) -> None:
        selected = self.program_tree.selection() if self.program_tree else ()
        if not selected:
            messagebox.showinfo("Désinstallation", "Sélectionne d'abord l'application dans la liste.")
            return
        name = self.program_tree.item(selected[0], "values")[0]
        try:
            self.clipboard_clear()
            self.clipboard_append(name)
            os.startfile("ms-settings:appsfeatures")
            messagebox.showinfo("Désinstallation Windows", f"Le nom « {name} » a été copié.\n\nTrouve l'application dans les paramètres Windows puis utilise Désinstaller.")
        except Exception as exc:
            messagebox.showerror("Désinstallation Windows", f"Impossible d'ouvrir les paramètres.\n\n{exc}")

    def _appearance_page(self) -> None:
        linux = IS_LINUX
        self._page_heading("Personnalisation · 05", "Apparence de l'outil" if linux else "Apparence Windows",
                           "Choisis une couleur pour l'interface DebloatCraft." if linux else "Choisis une couleur d'accent et applique-la au thème Windows.")
        card = self._card(self.page_content, "Couleurs rapides", "La modification concerne uniquement DebloatCraft." if linux else "La modification concerne l'accent Windows du compte courant.")
        card.pack(fill="x", padx=30, pady=(0, 16))
        swatches = tk.Frame(card, bg=PANEL)
        swatches.pack(anchor="w", padx=18, pady=(0, 14))
        for shade in PALETTE:
            tk.Button(swatches, bg=shade, activebackground=shade, width=4, height=2, bd=0,
                      command=lambda color=shade: self.select_accent(color), cursor="hand2").pack(side="left", padx=(0, 10))
        controls = tk.Frame(card, bg=PANEL)
        controls.pack(fill="x", padx=18, pady=(0, 18))
        self._button(controls, "Choisir une couleur…", self.choose_accent, False).pack(side="left")
        if not linux:
            self._button(controls, "Appliquer à Windows", self.apply_windows_accent).pack(side="left", padx=10)
        self.accent_preview = tk.Label(controls, text="   Aperçu   ", bg=self.accent, fg=accent_text_color(self.accent),
                                       font=("Segoe UI Semibold", 9), padx=10, pady=8)
        self.accent_preview.pack(side="right")
        note = self._card(self.page_content, "Réversible", "Les valeurs de couleur précédentes sont sauvegardées dans la configuration locale de DebloatCraft.")
        note.pack(fill="x", padx=30)

    def select_accent(self, shade: str) -> None:
        self.accent = shade
        self.config_data["accent"] = shade
        save_config(self.config_data)
        if hasattr(self, "accent_preview") and self.accent_preview.winfo_exists():
            self.accent_preview.configure(bg=shade, fg=accent_text_color(shade))

    def choose_accent(self) -> None:
        chosen = colorchooser.askcolor(color=self.accent, title="Couleur d'accent Windows", parent=self)
        if chosen and chosen[1]:
            self.select_accent(chosen[1])

    def apply_windows_accent(self) -> None:
        if not messagebox.askyesno("Couleur Windows", "Appliquer cette couleur d'accent au compte Windows courant?"):
            return
        try:
            self._remember_color_values()
            red, green, blue = (int(self.accent[index:index + 2], 16) for index in (1, 3, 5))
            abgr = 0xFF000000 | (blue << 16) | (green << 8) | red
            write_registry_value("HKCU", r"Software\Microsoft\Windows\DWM", "AccentColor", abgr, 4)
            write_registry_value("HKCU", r"Software\Microsoft\Windows\DWM", "ColorizationColor", abgr, 4)
            try:
                ctypes.windll.user32.SendMessageTimeoutW(
                    0xFFFF, 0x001A, 0, ctypes.c_wchar_p("ImmersiveColorSet"), 2, 1000, None,
                )
            except Exception:
                pass
            save_config(self.config_data)
            self.status_var.set(f"Accent Windows modifié · {self.accent}")
        except Exception as exc:
            messagebox.showerror("Couleur Windows", f"Impossible d'appliquer la couleur.\n\n{exc}")

    def _remember_color_values(self) -> None:
        backup = self.config_data.setdefault("registry_backup", {})
        for name in ("AccentColor", "ColorizationColor"):
            backup_id = f"HKCU|Software\\Microsoft\\Windows\\DWM|{name}"
            if backup_id not in backup:
                existed, value, value_type = read_registry_value("HKCU", r"Software\Microsoft\Windows\DWM", name)
                backup[backup_id] = {"root": "HKCU", "path": r"Software\Microsoft\Windows\DWM",
                                     "name": name, "existed": existed, "value": value, "type": value_type}

    def _profiles_page(self) -> None:
        self._page_heading("Profils · 06", "Profils de jeux", "Enregistre des palettes par jeu et applique l'accent choisi manuellement.")
        layout = tk.Frame(self.page_content, bg=BG)
        layout.pack(fill="both", expand=True, padx=30, pady=(0, 18))
        left = self._card(layout, "Profils enregistrés", "Les profils ne modifient pas automatiquement le jeu.")
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        self.profile_box = tk.Listbox(left, bg=PANEL_ALT, fg=TEXT, selectbackground="#303d66",
                                      selectforeground=TEXT, bd=0, highlightthickness=0,
                                      font=("Segoe UI", 10), activestyle="none")
        self.profile_box.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        self.profile_box.bind("<<ListboxSelect>>", self._select_profile)
        right = self._card(layout, "Créer / appliquer")
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.profile_name = tk.StringVar()
        tk.Label(right, text="Nom du jeu", fg=MUTED, bg=PANEL, font=("Segoe UI", 9)).pack(anchor="w", padx=18)
        tk.Entry(right, textvariable=self.profile_name, bg=PANEL_ALT, fg=TEXT, insertbackground=TEXT,
                 relief="flat", font=("Segoe UI", 10)).pack(fill="x", padx=18, pady=(5, 16), ipady=8)
        palette = tk.Frame(right, bg=PANEL)
        palette.pack(anchor="w", padx=18, pady=(0, 16))
        for shade in PALETTE:
            tk.Button(palette, bg=shade, activebackground=shade, width=3, height=1, bd=0,
                      command=lambda color=shade: self._choose_profile_color(color)).pack(side="left", padx=(0, 7))
        self._button(right, "Créer / mettre à jour", self.save_game_profile).pack(anchor="w", padx=18, pady=(0, 10))
        apply_label = "Appliquer la couleur à Windows" if os.name == "nt" else "Appliquer à DebloatCraft"
        self._button(right, apply_label, self.apply_selected_profile, False).pack(anchor="w", padx=18, pady=(0, 10))
        self._button(right, "Supprimer le profil", self.delete_game_profile, False).pack(anchor="w", padx=18, pady=(0, 18))
        self._refresh_profiles()

    def _choose_profile_color(self, shade: str) -> None:
        self.profile_color = shade

    def _refresh_profiles(self) -> None:
        if not self.profile_box:
            return
        self.profile_box.delete(0, tk.END)
        profiles = self.config_data.get("game_profiles", [])
        for profile in profiles:
            self.profile_box.insert(tk.END, f"{profile['name']}   ·   {profile['color']}")

    def _select_profile(self, _event: Any = None) -> None:
        if not self.profile_box or not self.profile_name:
            return
        selection = self.profile_box.curselection()
        if selection:
            profile = self.config_data.get("game_profiles", [])[selection[0]]
            self.profile_name.set(profile["name"])
            self.profile_color = profile["color"]

    def save_game_profile(self) -> None:
        if not self.profile_name:
            return
        name = self.profile_name.get().strip()
        if not name:
            messagebox.showinfo("Profil", "Entre le nom du jeu.")
            return
        profiles = self.config_data.setdefault("game_profiles", [])
        profile = {"name": name, "color": self.profile_color}
        for index, existing in enumerate(profiles):
            if existing["name"].casefold() == name.casefold():
                profiles[index] = profile
                break
        else:
            profiles.append(profile)
        save_config(self.config_data)
        self._refresh_profiles()
        self.status_var.set(f"Profil enregistré · {name}")

    def apply_selected_profile(self) -> None:
        if not self.profile_name or not self.profile_name.get().strip():
            messagebox.showinfo("Profil", "Sélectionne un profil enregistré.")
            return
        profile = next((item for item in self.config_data.get("game_profiles", [])
                        if item["name"].casefold() == self.profile_name.get().strip().casefold()), None)
        if profile:
            self.select_accent(profile["color"])
            if os.name == "nt":
                self.apply_windows_accent()
            else:
                self.status_var.set(f"Couleur appliquée à DebloatCraft · {profile['color']}")

    def delete_game_profile(self) -> None:
        if not self.profile_box or not self.profile_box.curselection():
            messagebox.showinfo("Profil", "Sélectionne un profil à supprimer.")
            return
        index = self.profile_box.curselection()[0]
        profiles = self.config_data.get("game_profiles", [])
        if index < len(profiles):
            del profiles[index]
            save_config(self.config_data)
            self._refresh_profiles()

    def _quiz_page(self) -> None:
        self._page_heading("Préférences · 07", "Ton style, en 5 questions", "Le quiz choisit le thème de DebloatCraft et une couleur d'accent. Il ne collecte rien.")
        card = self._card(self.page_content, "Préférences visuelles")
        card.pack(fill="both", expand=True, padx=30, pady=(0, 14))
        questions = [
            ("1. Quelle base te plaît le plus ?", ["Gris doux", "Noir profond", "Blanc lumineux"]),
            ("2. Quel contraste préfères-tu ?", ["Discret", "Équilibré", "Très contrasté"]),
            ("3. Les couleurs doivent être…", ["Naturelles", "Vives", "Très sobres"]),
            ("4. Quelle accentuation ?", ["Bleu", "Violet", "Vert", "Rose"]),
            ("5. Quel style de palette ?", ["Monochrome", "Dégradé bleu-violet", "Accent unique"]),
        ]
        self.quiz_answers: list[tk.StringVar] = []
        saved = self.config_data.get("quiz_answers", [])
        for index, (question, options) in enumerate(questions):
            row = tk.Frame(card, bg=PANEL)
            row.pack(fill="x", padx=18, pady=(10, 4))
            tk.Label(row, text=question, fg=TEXT, bg=PANEL,
                     font=("Segoe UI Semibold", 10)).pack(anchor="w")
            answer = tk.StringVar(value=saved[index] if index < len(saved) else options[0])
            self.quiz_answers.append(answer)
            for option in options:
                tk.Radiobutton(row, text=option, value=option, variable=answer, bg=PANEL, fg=MUTED,
                               activebackground=PANEL, activeforeground=TEXT, selectcolor=PANEL_ALT,
                               font=("Segoe UI", 9)).pack(side="left", padx=(0, 18), pady=3)
        self._button(card, "Voir mon thème", self.apply_quiz).pack(anchor="w", padx=18, pady=16)

    def apply_quiz(self) -> None:
        answers = [answer.get() for answer in self.quiz_answers]
        accent_choice = answers[3]
        choices = {"Bleu": "#4ca5ff", "Violet": "#9564ff", "Vert": "#65e6be", "Rose": "#ff5fa2"}
        chosen_accent = choices.get(accent_choice, BLUE)
        if answers[4] == "Monochrome" or answers[2] == "Très sobres":
            chosen_accent = "#747e92" if answers[0] == "Noir profond" else "#5c6577"
        elif answers[4] == "Dégradé bleu-violet":
            chosen_accent = "#807bff"
        self.select_accent(chosen_accent)
        self.config_data["color_mode"] = set_theme_palette(answers[0], answers[1])
        self.config_data["quiz_answers"] = answers
        self.config_data["visual_preference"] = {
            "base": answers[0], "contrast": answers[1], "saturation": answers[2], "palette": answers[4],
        }
        save_config(self.config_data)
        self.configure(bg=BG)
        self.workspace.configure(bg=BG)
        self.page_content.configure(bg=BG)
        self.header.configure(bg=BG)
        self._setup_styles()
        self.show_page("Vue d'ensemble")
        destination = "Windows dans Apparence" if os.name == "nt" else "l'interface DebloatCraft"
        messagebox.showinfo("Thème enregistré", f"Thème {answers[0]} enregistré. Accent: {chosen_accent}.\nTu peux aussi le modifier dans Apparence ({destination}).")


def main() -> int:
    if os.name != "nt" and not IS_LINUX:
        print("DebloatCraft prend en charge Windows et Linux.", file=sys.stderr)
        return 1
    try:
        app = DebloatCraftApp()
        app.mainloop()
        return 0
    except Exception as exc:
        messagebox.showerror(APP_NAME, f"L'application n'a pas pu démarrer.\n\n{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())