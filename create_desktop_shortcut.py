"""
Script para criar o atalho do MediaFinder na Área de Trabalho e Menu de Aplicativos (Windows e Linux).
"""

import os
import sys
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def create_shortcut_windows():
    exe_path = os.path.abspath(os.path.join("dist", "MediaFinder.exe"))
    if not os.path.exists(exe_path):
        exe_path = os.path.abspath("iniciar.bat")
    ico_path = os.path.abspath(os.path.join("assets", "icon.ico"))
    working_dir = os.path.abspath(".")

    desktop_dirs = [
        os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop"),
        os.path.join(os.path.expanduser("~"), "Desktop"),
        os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
    ]

    target_desktop = None
    for d in desktop_dirs:
        if os.path.exists(d):
            target_desktop = d
            break

    if not target_desktop:
        target_desktop = desktop_dirs[1]

    shortcut_path = os.path.join(target_desktop, "MediaFinder.lnk")

    ps_command = f"""
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut('{shortcut_path}')
    $Shortcut.TargetPath = '{exe_path}'
    $Shortcut.WorkingDirectory = '{working_dir}'
    $Shortcut.IconLocation = '{ico_path}, 0'
    $Shortcut.Description = 'MediaFinder — Buscador Rápido de Mídias Multi-HD'
    $Shortcut.Save()
    """

    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_command], check=True)
        print(f"✓ Atalho criado na Área de Trabalho com sucesso:")
        print(f"  👉 {shortcut_path}")
        return True
    except Exception as e:
        print(f"Erro ao criar atalho via PowerShell: {e}")
        return False


def create_shortcut_linux():
    working_dir = os.path.abspath(".")
    iniciar_sh = os.path.join(working_dir, "iniciar.sh")
    icon_path = os.path.abspath(os.path.join("assets", "icon.png"))

    desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=MediaFinder
GenericName=Buscador Rápido de Mídias & Modo TV
Comment=Localize, organize e reproduza mídias e canais de TV
Exec="{iniciar_sh}"
Icon={icon_path}
Path={working_dir}
Terminal=false
StartupNotify=true
Categories=AudioVideo;Player;Utility;
"""

    created_paths = []
    # 1. Menu de aplicativos do sistema (~/.local/share/applications)
    apps_dir = os.path.expanduser("~/.local/share/applications")
    os.makedirs(apps_dir, exist_ok=True)
    menu_desktop_file = os.path.join(apps_dir, "mediafinder.desktop")
    try:
        with open(menu_desktop_file, "w", encoding="utf-8") as f:
            f.write(desktop_content)
        os.chmod(menu_desktop_file, 0o755)
        created_paths.append(menu_desktop_file)
    except Exception as e:
        print(f"Erro ao criar atalho no menu: {e}")

    # 2. Área de Trabalho / Desktop
    desktop_candidates = [
        os.path.expanduser("~/Área de trabalho"),
        os.path.expanduser("~/Desktop")
    ]
    for d in desktop_candidates:
        if os.path.exists(d):
            dt_file = os.path.join(d, "MediaFinder.desktop")
            try:
                with open(dt_file, "w", encoding="utf-8") as f:
                    f.write(desktop_content)
                os.chmod(dt_file, 0o755)
                created_paths.append(dt_file)
            except Exception as e:
                print(f"Erro ao criar atalho no desktop: {e}")
            break

    if created_paths:
        print("✓ Atalhos do MediaFinder criados com sucesso no Linux:")
        for p in created_paths:
            print(f"  👉 {p}")
        return True
    return False


def create_shortcut():
    if sys.platform == "win32":
        return create_shortcut_windows()
    else:
        return create_shortcut_linux()


if __name__ == "__main__":
    create_shortcut()

