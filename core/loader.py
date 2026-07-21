"""Extract plain text from documents (PDF, DOCX, TXT, MD, CSV)."""
from __future__ import annotations

from pathlib import Path

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".txt", ".md", ".csv")


def load_document(path: str | Path) -> list[dict]:
    """Return a list of text blocks: {"page": int | None, "text": str}."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix == ".docx":
        return _load_docx(path)
    if suffix in (".txt", ".md", ".csv"):
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
        return [{"page": None, "text": text}] if text else []
    raise ValueError(f"Unsupported file type: {suffix} (supported: {', '.join(SUPPORTED_EXTENSIONS)})")


def _load_pdf(path: Path) -> list[dict]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    blocks = []
    for page_no, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            blocks.append({"page": page_no, "text": text})
    if not blocks:
        raise ValueError(
            f"No selectable text in {path.name} — looks like a scanned PDF (OCR not supported in this POC)."
        )
    return blocks


def _load_docx(path: Path) -> list[dict]:
    import docx

    document = docx.Document(str(path))
    parts = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    text = "\n".join(parts).strip()
    return [{"page": None, "text": text}] if text else []
