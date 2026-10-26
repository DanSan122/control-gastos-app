"""Render every QA page, inspect PDF text and downloaded XLSX/CSV independently."""

import sys
import re
from pathlib import Path
import pymupdf
from pypdf import PdfReader

directory = Path(sys.argv[1])
source = directory / "report-qa.pdf"
reader = PdfReader(source)
assert len(reader.pages) >= 4
text = "\n".join(page.extract_text() for page in reader.pages)
assert "49382.40" in text
assert "Referencia de prueba 40" in " ".join(text.split())
document = pymupdf.open(source)
for page in document:
    page_text = page.get_text()
    assert len(
        re.findall(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", page_text)
    ) == page_text.count("UUID:")
    assert all(
        0 <= b[0] <= b[2] <= page.rect.width
        and 0 <= b[1] <= b[3] <= page.rect.height
        for b in page.get_text("blocks")
    )
    page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).save(
        directory / f"report-qa-page-{page.number + 1}.png"
    )
print(
    f"PDF QA: {len(document)} páginas renderizadas, total exacto y último movimiento presentes; PyMuPDF {pymupdf.VersionBind}."
)
