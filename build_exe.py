"""
Script para compilar o MediaFinder em um Executável (.exe) do Windows usando PyInstaller.
Execute: python build_exe.py
"""

import os
import sys
import subprocess
import shutil

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def build():
    is_windows = sys.platform == "win32"
    platform_name = "Windows (.exe)" if is_windows else "Linux"
    print("=" * 60)
    print(f"🚀 Iniciando compilação do MediaFinder para {platform_name}...")
    print("=" * 60)

    sep = ";" if is_windows else ":"
    icon_file = "assets/icon.ico" if is_windows else "assets/icon.png"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=MediaFinder",
        "--noconsole",
        "--onefile",
        "--noconfirm",
        f"--icon={icon_file}",
        f"--add-data=assets{sep}assets",
        "--collect-all=PySide6",
        "--collect-all=PIL",
        "main.py"
    ]

    print(f"Executando comando: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        binary_name = "MediaFinder.exe" if is_windows else "MediaFinder"
        exe_path = os.path.abspath(os.path.join("dist", binary_name))
        print("\n" + "=" * 60)
        print("🎉 COMPILAÇÃO CONCLUÍDA COM SUCESSO!")
        print(f"📁 O binário foi gerado em: {exe_path}")
        print("=" * 60)
    else:
        print("\n❌ Ocorreu um erro durante a compilação.")


if __name__ == "__main__":
    build()
