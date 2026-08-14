#!/usr/bin/env python3
"""Home Server system tray indicator with dynamic state-aware menu."""

import shutil
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

HOME_SERVER = Path(__file__).resolve().parent.parent
CATEGORY_SH = HOME_SERVER / "scripts" / "category.sh"
UPDATE_SH = HOME_SERVER / "scripts" / "update.sh"

# Terminal emulators in preference order (KDE Plasma → konsole first).
# Each entry: (binary name, argv prefix to run a command).
TERMINALS = [
    ("konsole",        ["konsole", "-e"]),
    ("gnome-terminal", ["gnome-terminal", "--"]),
    ("xterm",          ["xterm", "-e"]),
]


def find_terminal() -> list[str] | None:
    """Return argv prefix for the first available terminal, or None."""
    for binary, prefix in TERMINALS:
        if shutil.which(binary):
            return prefix
    return None

SECTIONS = ["forge", "sillytavern", "dashboard", "media", "ebooks", "asf"]
SECTION_CONTAINERS = {
    "forge": "home-forge",
    "sillytavern": "home-sillytavern",
    "dashboard": "home-dashboard",
    "media": "jellyfin",
    "ebooks": "home-ebooks",
    "asf": "home-asf",
}

CATEGORIES = {
    "ai": ("AI (Forge + ST)", ["forge", "sillytavern"]),
    "media": ("Media", ["media"]),
    "ebooks": ("Ebooks", ["ebooks"]),
    "asf": ("ASF (Steam)", ["asf"]),
}


def is_section_up(section: str) -> bool:
    container = SECTION_CONTAINERS.get(section)
    if not container:
        return False
    result = subprocess.run(
        ["podman", "ps", "--filter", f"name={container}", "--format", "{{.Names}}"],
        capture_output=True, text=True, check=False,
    )
    return container in result.stdout


def all_states() -> dict[str, bool]:
    return {s: is_section_up(s) for s in SECTIONS}


def make_dot_icon(color: str) -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(8, 8, 48, 48)
    painter.end()
    return QIcon(pix)


class HomeServerTray(QSystemTrayIcon):
    def __init__(self, app: QApplication):
        super().__init__(app)
        self.app = app
        self.menu = QMenu()
        self.menu.aboutToShow.connect(self.rebuild_menu)
        self.setContextMenu(self.menu)
        self.activated.connect(self._on_activated)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_icon_and_tooltip)
        self.timer.start(5000)
        self.update_icon_and_tooltip()

    def update_icon_and_tooltip(self):
        states = all_states()
        up = sum(1 for v in states.values() if v)
        total = len(states)
        if up == total:
            color = "#22c55e"  # green: all up
        elif up == 0:
            color = "#6b7280"  # gray: all off
        else:
            color = "#eab308"  # yellow: partial
        self.setIcon(make_dot_icon(color))
        lines = [f"Home Server: {up}/{total} up"]
        for s in SECTIONS:
            lines.append(f"{'●' if states[s] else '○'} {s}")
        self.setToolTip("\n".join(lines))

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_dashboard()

    def rebuild_menu(self):
        self.menu.clear()
        states = all_states()
        up = sum(1 for v in states.values() if v)
        total = len(states)

        header = self.menu.addAction(f"Home Server — {up}/{total} up")
        header.setEnabled(False)
        self.menu.addSeparator()

        for s in SECTIONS:
            self.menu.addAction(f"{'●' if states[s] else '○'} {s}").setEnabled(False)
        self.menu.addSeparator()

        if states["dashboard"]:
            self.menu.addAction("Open Dashboard").triggered.connect(self.open_dashboard)
        else:
            self.menu.addAction("Start Dashboard").triggered.connect(
                lambda: self.run_section("dashboard", "up")
            )

        self.menu.addSeparator()

        for cat, (label, sections) in CATEGORIES.items():
            cat_up = sum(1 for s in sections if states[s])
            if cat_up < len(sections):
                self.menu.addAction(f"Start {label}").triggered.connect(
                    lambda checked=False, c=cat: self.run_category(c, "up")
                )
            if cat_up > 0:
                self.menu.addAction(f"Stop {label}").triggered.connect(
                    lambda checked=False, c=cat: self.run_category(c, "down")
                )

        if up < total:
            self.menu.addAction("Start All").triggered.connect(
                lambda: self.run_category("all", "up")
            )
        if up > 0:
            self.menu.addAction("Stop All").triggered.connect(
                lambda: self.run_category("all", "down")
            )

        self.menu.addSeparator()
        self.menu.addAction("Update Services").triggered.connect(self.run_update)
        self.menu.addAction("Refresh").triggered.connect(self.update_icon_and_tooltip)
        self.menu.addAction("Quit Tray").triggered.connect(self.app.quit)

    def run_section(self, section: str, action: str):
        subprocess.Popen(
            [str(HOME_SERVER / "scripts" / f"{action}.sh"), section],
            cwd=str(HOME_SERVER),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        QTimer.singleShot(3000, self.update_icon_and_tooltip)

    def run_category(self, category: str, action: str):
        subprocess.Popen(
            [str(CATEGORY_SH), category, action],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        QTimer.singleShot(3000, self.update_icon_and_tooltip)

    def open_dashboard(self):
        if not is_section_up("dashboard"):
            self.run_section("dashboard", "up")
            QTimer.singleShot(5000, lambda: subprocess.Popen(["xdg-open", "http://localhost:7575"]))
        else:
            subprocess.Popen(["xdg-open", "http://localhost:7575"])

    def run_update(self):
        # Pull is slow + interactive (recycle prompt) — surface in a terminal.
        term = find_terminal()
        if term is None:
            self.showMessage(
                "Home Server",
                "No terminal emulator found (konsole/gnome-terminal/xterm). "
                f"Run manually: {UPDATE_SH}",
                QSystemTrayIcon.MessageIcon.Critical,
            )
            return
        subprocess.Popen(
            term + [str(UPDATE_SH)],
            cwd=str(HOME_SERVER),
        )
        # Recycle (if user accepts) takes ~1-2 min — re-poll soon after.
        QTimer.singleShot(120_000, self.update_icon_and_tooltip)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("System tray not available", file=sys.stderr)
        sys.exit(1)
    tray = HomeServerTray(app)
    tray.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
