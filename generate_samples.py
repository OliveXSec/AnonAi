"""Generate synthetic sample files for integration testing.

All PII values are fake and designed to NOT trigger GitHub Secret Scanning.
Run this script to regenerate the samples/ directory.
"""

from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.shared import Pt
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

SAMPLES = Path(__file__).parent / "samples"

SLACK_TOKEN = "xoxb-fake-slack-test-token-1234"
GITHUB_TOKEN = "ghp_TestToken00000000000000000000000fake"
AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
OPENAI_KEY = "sk-test00000000000000000000000000000000000fake"

EXPECTED = {
    "_note": "*** SYNTHETIC TEST DATA — NOT REAL — FOR PII SCRUBBER TESTING ONLY ***",
    "_description": "Ground truth of PII entities the scrubber must detect in sample files. 100% synthetic values.",
    "expected_entities": {
        "PERSON": ["Juan Perez", "Maria Gonzalez"],
        "EMAIL": ["juan.perez@example.com", "maria.gonzalez@example.org"],
        "PHONE": ["+54 9 381 555-0142", "+54 11 4555-0188"],
        "CUIT_CUIL": ["20-30111222-0", "27-28999888-3", "30-71234567-1"],
        "DNI": ["30111222", "28999888"],
        "IP_ADDRESS": ["192.0.2.14", "198.51.100.7"],
        "CREDIT_CARD": [
            "4111 1111 1111 1111",
            "5555 5555 5555 4444",
            "3782 822463 10005",
        ],
        "AWS_KEY": [AWS_KEY],
        "GITHUB_TOKEN": [GITHUB_TOKEN],
        "SLACK_TOKEN": [SLACK_TOKEN],
        "API_KEY": [OPENAI_KEY],
        "LOCATION": ["Yerba Buena", "Tucuman", "Buenos Aires"],
        "ORG": ["OliveX Security", "Banco Sintetico S.A."],
    },
}


def generate_pdf() -> None:
    path = SAMPLES / "sample_pii.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    w, h = letter
    y = h - 72

    def line(text: str, size: float = 10) -> None:
        nonlocal y
        c.setFont("Helvetica", size)
        c.drawString(72, y, text)
        y -= size + 6

    line("*** SYNTHETIC TEST DATA -- NOT REAL -- FOR PII SCRUBBER TESTING ONLY ***", 8)
    line("Ficha de Cliente (Muestra de Prueba)", 14)
    line("Documento generado para testear un anonimizador de PII. Todos los datos son sinteticos y no")
    line("pertenecen a personas reales.")
    y -= 10

    line("Registro 1: Juan Perez", 12)
    for label, val in [
        ("Nombre completo", "Juan Perez"),
        ("Email", "juan.perez@example.com"),
        ("Telefono", "+54 9 381 555-0142"),
        ("CUIT", "20-30111222-0"),
        ("DNI", "30111222"),
        ("IP de ultimo acceso", "192.0.2.14"),
        ("Tarjeta de credito", "4111 1111 1111 1111"),
    ]:
        line(f"{label}: {val}")
    y -= 10

    line("Registro 2: Maria Gonzalez", 12)
    for label, val in [
        ("Nombre completo", "Maria Gonzalez"),
        ("Email", "maria.gonzalez@example.org"),
        ("Telefono", "+54 11 4555-0188"),
        ("CUIT", "27-28999888-3"),
        ("DNI", "28999888"),
        ("IP de ultimo acceso", "198.51.100.7"),
        ("Tarjeta de credito", "5555 5555 5555 4444"),
    ]:
        line(f"{label}: {val}")
    y -= 10

    line("Notas de la cuenta", 12)
    line("El cliente Juan Perez, domiciliado en Yerba Buena, Tucuman, fue contactado por el equipo de OliveX")
    line("Security. La cuenta secundaria de Maria Gonzalez figura en Buenos Aires y esta vinculada a Banco")
    line("Sintetico S.A. El CUIT de la empresa es 30-71234567-1. Cualquier coincidencia con datos reales es")
    line("involuntaria: este documento es material de prueba.")
    y -= 10

    line("Fragmento de configuracion (simulado)", 12)
    line(f"aws_key = {AWS_KEY}")
    line(f"github_token = {GITHUB_TOKEN}")
    line(f"slack_token = {SLACK_TOKEN}")
    line(f"openai_key = {OPENAI_KEY}")
    line("amex_de_respaldo = 3782 822463 10005")
    y -= 10

    line("*** SYNTHETIC TEST DATA -- NOT REAL -- FOR PII SCRUBBER TESTING ONLY ***", 8)
    c.showPage()

    y = h - 72
    line("Pagina 2: CUIT 30-71234567-1", 12)
    c.showPage()
    c.save()


def generate_docx() -> None:
    path = SAMPLES / "sample_pii.docx"
    doc = Document()

    style = doc.styles["Normal"]
    style.font.size = Pt(10)

    doc.add_paragraph("*** SYNTHETIC TEST DATA -- NOT REAL -- FOR PII SCRUBBER TESTING ONLY ***")
    doc.add_paragraph("Ficha de Cliente (Muestra de Prueba)")
    doc.add_paragraph("Documento generado para testear un anonimizador de PII. Todos los datos son sinteticos.")

    doc.add_paragraph("Registro 1: Juan Perez")
    doc.add_paragraph("Registro 2: Maria Gonzalez")

    doc.add_paragraph("Notas de la cuenta")
    doc.add_paragraph(
        "El cliente Juan Perez, domiciliado en Yerba Buena, Tucuman, fue contactado por el equipo de "
        "OliveX Security. La cuenta secundaria de Maria Gonzalez figura en Buenos Aires y esta vinculada "
        "a Banco Sintetico S.A. El CUIT de la empresa es 30-71234567-1."
    )

    doc.add_paragraph("Fragmento de configuracion (simulado)")
    doc.add_paragraph(f"aws_key = {AWS_KEY}")
    doc.add_paragraph(f"github_token = {GITHUB_TOKEN}")
    doc.add_paragraph(f"slack_token = {SLACK_TOKEN}")
    doc.add_paragraph(f"openai_key = {OPENAI_KEY}")
    doc.add_paragraph("amex_de_respaldo = 3782 822463 10005")

    doc.add_paragraph("*** SYNTHETIC TEST DATA -- NOT REAL -- FOR PII SCRUBBER TESTING ONLY ***")

    table1 = doc.add_table(rows=8, cols=2)
    table1.style = "Table Grid"
    data1 = [
        ("Campo", "Valor"),
        ("Nombre completo", "Juan Perez"),
        ("Email", "juan.perez@example.com"),
        ("Telefono", "+54 9 381 555-0142"),
        ("CUIT", "20-30111222-0"),
        ("DNI", "30111222"),
        ("IP de ultimo acceso", "192.0.2.14"),
        ("Tarjeta de credito", "4111 1111 1111 1111"),
    ]
    for i, (k, v) in enumerate(data1):
        table1.cell(i, 0).text = k
        table1.cell(i, 1).text = v

    table2 = doc.add_table(rows=8, cols=2)
    table2.style = "Table Grid"
    data2 = [
        ("Campo", "Valor"),
        ("Nombre completo", "Maria Gonzalez"),
        ("Email", "maria.gonzalez@example.org"),
        ("Telefono", "+54 11 4555-0188"),
        ("CUIT", "27-28999888-3"),
        ("DNI", "28999888"),
        ("IP de ultimo acceso", "198.51.100.7"),
        ("Tarjeta de credito", "5555 5555 5555 4444"),
    ]
    for i, (k, v) in enumerate(data2):
        table2.cell(i, 0).text = k
        table2.cell(i, 1).text = v

    doc.save(str(path))


def _get_font(size: int = 16):
    try:
        return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
    except (OSError, IOError):
        return ImageFont.load_default()


def generate_form_image() -> None:
    path = SAMPLES / "sample_form.png"
    img = Image.new("RGB", (700, 500), color="white")
    draw = ImageDraw.Draw(img)
    font = _get_font(16)
    small = _get_font(12)

    draw.text((10, 10), "SYNTHETIC TEST DATA - NOT REAL - PII SCRUBBER TESTING ONLY", fill="gray", font=small)
    draw.text((10, 35), "OliveX CRM / Detalle de Cliente", fill="black", font=_get_font(20))

    y = 80
    fields = [
        ("Nombre:", "Juan Perez"),
        ("Email:", "juan.perez@example.com"),
        ("Telefono:", "+54 9 381 555-0142"),
        ("CUIT:", "20-30111222-0"),
        ("DNI:", "30111222"),
        ("IP acceso:", "192.0.2.14"),
        ("Tarjeta:", "4111 1111 1111 1111"),
        ("API key:", OPENAI_KEY),
    ]
    for label, value in fields:
        draw.text((10, y), label, fill="black", font=font)
        draw.text((200, y), value, fill="black", font=font)
        y += 40

    img.save(str(path))


def generate_id_image() -> None:
    path = SAMPLES / "sample_id.png"
    img = Image.new("RGB", (600, 350), color="#f0f0f0")
    draw = ImageDraw.Draw(img)
    font = _get_font(16)
    small = _get_font(12)
    title_font = _get_font(14)

    draw.text((10, 10), "REPUBLICA SINTETICA - DOCUMENTO DE MUESTRA", fill="black", font=title_font)

    draw.text((10, 50), "APELLIDO Y NOMBRE", fill="gray", font=small)
    draw.text((10, 70), "Maria Gonzalez", fill="black", font=font)

    draw.text((10, 110), "DNI", fill="gray", font=small)
    draw.text((10, 130), "28999888", fill="black", font=font)

    draw.text((10, 170), "CUIL", fill="gray", font=small)
    draw.text((10, 190), "27-28999888-3", fill="black", font=font)

    draw.text((10, 230), "DOMICILIO", fill="gray", font=small)
    draw.text((10, 250), "Av. Siempreviva 742, Buenos Aires", fill="black", font=font)

    draw.text((10, 290), "EMAIL", fill="gray", font=small)
    draw.text((10, 310), "maria.gonzalez@example.org", fill="black", font=font)

    img.save(str(path))


def generate_expected() -> None:
    path = SAMPLES / "expected.json"
    with open(path, "w") as f:
        json.dump(EXPECTED, f, indent=2, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    SAMPLES.mkdir(exist_ok=True)
    generate_pdf()
    generate_docx()
    generate_form_image()
    generate_id_image()
    generate_expected()
    print(f"[+] Generated samples in {SAMPLES}/")
