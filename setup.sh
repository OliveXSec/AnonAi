#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "[*] Verificando Homebrew..."
if ! command -v brew &>/dev/null; then
    echo "[-] Homebrew no encontrado. Instalalo desde https://brew.sh"
    exit 1
fi

echo "[*] Instalando Tesseract + idiomas..."
brew install tesseract tesseract-lang 2>/dev/null || brew upgrade tesseract tesseract-lang 2>/dev/null || true

echo "[*] Creando virtual environment..."
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" &>/dev/null; then
        version=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major="${version%%.*}"
        minor="${version##*.}"
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[-] Se requiere Python >= 3.10. Instalá con: brew install python@3.13"
    exit 1
fi

echo "[*] Usando $PYTHON ($("$PYTHON" --version))"

if [ ! -d .venv ]; then
    "$PYTHON" -m venv .venv
fi

echo "[*] Instalando dependencias Python..."
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

echo "[*] Descargando modelo spaCy es_core_news_lg..."
.venv/bin/python -m spacy download es_core_news_lg --quiet 2>/dev/null || \
    .venv/bin/python -m spacy download es_core_news_lg

echo "[*] Verificando instalación..."
.venv/bin/python -c "
from anonymizer import Anonymizer
anon = Anonymizer()
r = anon.anonymize('Test: user@mail.com')
assert '[EMAIL_ADDRESS_1]' in r.text
print('[+] Anonymizer OK')

from readers import read_file
print('[+] Readers OK')

import pytesseract
v = pytesseract.get_tesseract_version()
print(f'[+] Tesseract {v} OK')
"

echo ""
echo "[+] Instalación completa. Uso:"
echo "    source .venv/bin/activate"
echo "    python -c \"from anonymizer import Anonymizer; print(Anonymizer().anonymize('Juan Pérez, juan@test.com').text)\""
echo ""
echo "[+] Tests:"
echo "    .venv/bin/python -m pytest tests/ -v"
