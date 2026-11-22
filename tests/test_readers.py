"""Tests for file readers and Anonymizer file methods."""

from __future__ import annotations

from pathlib import Path

import pytest

from readers import read_file, read_directory


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module", autouse=True)
def create_fixtures() -> None:
    """Create test fixture files."""
    FIXTURES.mkdir(exist_ok=True)
    _create_txt()
    _create_pdf()
    _create_docx()
    _create_image()
    _create_subdir()


def _create_txt() -> None:
    (FIXTURES / "sample.txt").write_text(
        "Juan Pérez, email: juan@test.com, IP: 10.0.0.1\n",
        encoding="utf-8",
    )


def _create_pdf() -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    path = FIXTURES / "sample.pdf"
    c = canvas.Canvas(str(path), pagesize=letter)
    c.drawString(72, 700, "Nombre: María López, DNI: 35678901")
    c.drawString(72, 680, "Email: maria@empresa.com")
    c.showPage()
    c.drawString(72, 700, "Página 2: CUIT 20-12345678-6")
    c.showPage()
    c.save()


def _create_docx() -> None:
    from docx import Document

    doc = Document()
    doc.add_paragraph("Informe confidencial")
    doc.add_paragraph("Cliente: Carlos Ruiz, email: carlos@corp.com")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Nombre"
    table.cell(0, 1).text = "DNI"
    table.cell(1, 0).text = "Ana García"
    table.cell(1, 1).text = "40123456"
    doc.save(str(FIXTURES / "sample.docx"))


def _create_image() -> None:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (400, 100), color="white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
    except (OSError, IOError):
        font = ImageFont.load_default()
    draw.text((10, 30), "Email: test@example.com", fill="black", font=font)
    img.save(str(FIXTURES / "sample.png"))


def _create_subdir() -> None:
    sub = FIXTURES / "subdir"
    sub.mkdir(exist_ok=True)
    (sub / "nested.txt").write_text(
        "Contacto: nested@mail.com\n", encoding="utf-8"
    )


class TestReadFile:
    def test_read_txt(self) -> None:
        text = read_file(FIXTURES / "sample.txt")
        assert "Juan Pérez" in text
        assert "juan@test.com" in text

    def test_read_pdf(self) -> None:
        text = read_file(FIXTURES / "sample.pdf")
        assert "María" in text or "Maria" in text
        assert "maria@empresa.com" in text

    def test_read_pdf_specific_pages(self) -> None:
        text = read_file(FIXTURES / "sample.pdf", pages=[1])
        assert "CUIT" in text
        assert "maria@empresa.com" not in text

    def test_read_docx(self) -> None:
        text = read_file(FIXTURES / "sample.docx")
        assert "Carlos Ruiz" in text
        assert "carlos@corp.com" in text
        assert "Ana García" in text or "Ana Garcia" in text

    def test_read_image(self) -> None:
        text = read_file(FIXTURES / "sample.png", lang="eng")
        assert "test@example.com" in text or "example" in text.lower()

    def test_unsupported_format(self) -> None:
        fake = FIXTURES / "fake.xyz"
        fake.write_text("data")
        with pytest.raises(ValueError, match="Formato no soportado"):
            read_file(fake)
        fake.unlink()

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            read_file("/nonexistent/file.pdf")


class TestReadDirectory:
    def test_reads_all_files(self) -> None:
        results = read_directory(FIXTURES)
        assert any("sample.txt" in k for k in results)
        assert any("sample.pdf" in k for k in results)
        assert any("sample.docx" in k for k in results)

    def test_filter_by_extension(self) -> None:
        results = read_directory(FIXTURES, extensions=[".txt"])
        assert all(k.endswith(".txt") for k in results)

    def test_recursive(self) -> None:
        results = read_directory(FIXTURES, extensions=[".txt"], recursive=True)
        nested = [k for k in results if "nested" in k]
        assert len(nested) == 1
        assert "nested@mail.com" in results[nested[0]]

    def test_non_recursive_skips_subdir(self) -> None:
        results = read_directory(FIXTURES, extensions=[".txt"], recursive=False)
        nested = [k for k in results if "nested" in k]
        assert len(nested) == 0

    def test_not_a_directory(self) -> None:
        with pytest.raises(NotADirectoryError):
            read_directory(FIXTURES / "sample.txt")


class TestAnonymizerFile:
    @pytest.fixture(scope="class")
    def anon(self):
        from anonymizer import Anonymizer
        return Anonymizer(reversible=True)

    def test_anonymize_file_txt(self, anon) -> None:
        result = anon.anonymize_file(FIXTURES / "sample.txt")
        assert "juan@test.com" not in result.text
        assert "[EMAIL_ADDRESS_" in result.text

    def test_anonymize_file_pdf(self, anon) -> None:
        result = anon.anonymize_file(FIXTURES / "sample.pdf")
        assert "maria@empresa.com" not in result.text

    def test_anonymize_file_docx(self, anon) -> None:
        result = anon.anonymize_file(FIXTURES / "sample.docx")
        assert "carlos@corp.com" not in result.text

    def test_anonymize_directory(self, anon) -> None:
        results = anon.anonymize_directory(FIXTURES, extensions=[".txt"])
        assert len(results) >= 1
        for _path, res in results.items():
            assert "[" in res.text

    def test_roundtrip_from_file(self, anon) -> None:
        result = anon.anonymize_file(FIXTURES / "sample.txt")
        assert result.mapping is not None
        restored = anon.restore(result.text, result.mapping)
        assert "juan@test.com" in restored
