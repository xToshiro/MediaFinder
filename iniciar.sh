#!/usr/bin/env bash
# Script para iniciar o MediaFinder no Linux (Regata OS / openSUSE / Ubuntu / Fedora)

set -e
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Prioriza o ambiente virtual local .venv se existir
if [ -f "$DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "❌ Erro: Python 3 não foi encontrado no sistema."
    exit 1
fi

echo "🚀 Iniciando o MediaFinder..."
exec "$PYTHON_BIN" "$DIR/main.py" "$@"
