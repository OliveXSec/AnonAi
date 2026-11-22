"""File readers for extracting text from PDF, DOCX, and images."""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def read_pdf(path: str | Path, pages: Optional[list[int]] = None) -> str:
    """Extract text from a PDF file.

    Args:
        path: Path to the PDF file.
        pages: Optional list of 0-indexed page numbers to extract. None = all pages.
    """
    try:
        import pdfplumber
    except ImportError as e:
        raise ImportError("pdfplumber no está instalado: pip install pdfplumber") from e

    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        target_pages = pdf.pages if pages is None else [pdf.pages[i] for i in pages]
        for page in target_pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return "\n".join(parts)


def read_docx(path: str | Path) -> str:
    """Extract text from a DOCX file, including tables."""
    try:
        from docx import Document
    except ImportError as e:
        raise ImportError("python-docx no está instalado: pip install python-docx") from e

    doc = Document(str(path))
    parts: list[str] = []

    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            parts.append(paragraph.text)

    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))

    return "\n".join(parts)


def read_image(path: str | Path, lang: str = "spa") -> str:
    """Extract text from an image via OCR (Tesseract).

    Args:
        path: Path to the image file (PNG, JPG, TIFF, BMP).
        lang: Tesseract language code. Default 'spa' for Spanish.
    """
    try:
        import pytesseract
    except ImportError as e:
        raise ImportError("pytesseract no está instalado: pip install pytesseract") from e
    try:
        from PIL import Image
    except ImportError as e:
        raise ImportError("Pillow no está instalado: pip install Pillow") from e

    try:
        pytesseract.get_tesseract_version()
    except pytesseract.TesseractNotFoundError as e:
        raise RuntimeError(
            "Tesseract no encontrado en el sistema.\n"
            "  macOS: brew install tesseract\n"
            "  Linux: apt install tesseract-ocr\n"
            "  Para español: brew install tesseract-lang  (o apt install tesseract-ocr-spa)"
        ) from e

    img = Image.open(str(path))
    return pytesseract.image_to_string(img, lang=lang).strip()


EXTENSION_MAP: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".tiff": "image",
    ".tif": "image",
    ".bmp": "image",
    ".webp": "image",
}

READERS = {
    "pdf": read_pdf,
    "docx": read_docx,
    "image": read_image,
}


def read_file(path: str | Path, **kwargs) -> str:
    """Auto-detect file type and extract text.

    Supports: .pdf, .docx, .png, .jpg, .jpeg, .tiff, .bmp, .webp, .txt
    Extra kwargs are passed to the specific reader (e.g. pages=[0,1] for PDF, lang='eng' for OCR).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {path}")

    ext = path.suffix.lower()

    if ext == ".txt":
        return path.read_text(encoding="utf-8")

    reader_type = EXTENSION_MAP.get(ext)
    if reader_type is None:
        raise ValueError(
            f"Formato no soportado: '{ext}'. "
            f"Soportados: {', '.join(sorted(set(['.txt'] + list(EXTENSION_MAP.keys()))))}"
        )

    reader = READERS[reader_type]
    supported_params = {"pdf": {"pages"}, "image": {"lang"}}.get(reader_type, set())
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in supported_params}
    return reader(path, **filtered_kwargs)


def read_directory(
    directory: str | Path,
    extensions: Optional[list[str]] = None,
    recursive: bool = False,
    **kwargs,
) -> dict[str, str]:
    """Read all supported files from a directory.

    Args:
        directory: Path to directory.
        extensions: Filter by extensions (e.g. ['.pdf', '.docx']). None = all supported.
        recursive: If True, search subdirectories.

    Returns:
        Dict mapping file path (str) to extracted text.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(f"No es un directorio: {directory}")

    all_extensions = set(EXTENSION_MAP.keys()) | {".txt"}
    if extensions is not None:
        target_exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
    else:
        target_exts = all_extensions

    pattern = "**/*" if recursive else "*"
    results: dict[str, str] = {}

    for file_path in sorted(directory.glob(pattern)):
        if file_path.is_file() and file_path.suffix.lower() in target_exts:
            try:
                results[str(file_path)] = read_file(file_path, **kwargs)
            except Exception as e:
                results[str(file_path)] = f"[ERROR: {e}]"

    return results
