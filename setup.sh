#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ---------- Tesseract (OCR de imágenes, opcional) ----------
install_tesseract() {
    if command -v tesseract &>/dev/null; then
        echo "[*] Tesseract ya instalado: $(tesseract --version 2>&1 | head -1)"
        return 0
    fi

    case "$(uname -s)" in
        Darwin)
            if command -v brew &>/dev/null; then
                echo "[*] Instalando Tesseract + idiomas (Homebrew)..."
                brew install tesseract tesseract-lang
            else
                echo "[!] Homebrew no encontrado. Para OCR de imágenes instalá Tesseract:"
                echo "      https://brew.sh  &&  brew install tesseract tesseract-lang"
            fi
            ;;
        Linux)
            if command -v apt-get &>/dev/null; then
                echo "[*] Instalando Tesseract + español (apt)..."
                sudo apt-get update -qq && sudo apt-get install -y tesseract-ocr tesseract-ocr-spa
            elif command -v dnf &>/dev/null; then
                echo "[*] Instalando Tesseract + español (dnf)..."
                sudo dnf install -y tesseract tesseract-langpack-spa
            else
                echo "[!] Gestor de paquetes no reconocido. Para OCR instalá tesseract-ocr y el idioma spa."
            fi
            ;;
        *)
            echo "[!] SO no reconocido. Para OCR de imágenes instalá Tesseract manualmente."
            ;;
    esac
}

install_tesseract

# ---------- Python ----------
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
    echo "[-] Se requiere Python >= 3.10."
    echo "    macOS: brew install python@3.13 | Linux: apt install python3.12 python3.12-venv"
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

# ---------- Verificación ----------
echo "[*] Verificando instalación..."
.venv/bin/python -c "
from anonymizer import Anonymizer
anon = Anonymizer()
r = anon.anonymize('Test: user@mail.com')
assert '[EMAIL_ADDRESS_1]' in r.text
print('[+] Anonymizer OK')

from readers import read_file  # noqa: F401
print('[+] Readers OK')

try:
    import pytesseract
    print(f'[+] Tesseract {pytesseract.get_tesseract_version()} OK')
except Exception as e:
    print(f'[!] OCR de imágenes no disponible ({e.__class__.__name__}). El resto funciona igual.')
"

echo ""
echo "[+] Instalación completa. Uso:"
echo "    source .venv/bin/activate"
echo "    python -c \"from anonymizer import Anonymizer; print(Anonymizer().anonymize('Juan Pérez, juan@test.com').text)\""
echo ""
echo "[+] Tests:"
echo "    .venv/bin/python -m pytest tests/ -v"
