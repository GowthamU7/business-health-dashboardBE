import io
from pypdf import PdfReader


def extract_text_from_pdf_bytes(content: bytes) -> str:
    pdf_stream = io.BytesIO(content)
    reader = PdfReader(pdf_stream)

    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text.strip())

    return "\n\n".join(pages).strip()