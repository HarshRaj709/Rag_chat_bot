# knowledge_base/utils.py
import os
import io
import docx
import pypdf



def extract_text(content: bytes, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()

    if ext in [".txt", ".md"]:
        return content.decode("utf-8", errors="ignore")

    elif ext == ".pdf":
        reader = pypdf.PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages).strip()
        if not text:
            raise ValueError("PDF appears to be scanned or has no extractable text.")
        return text

    elif ext == ".docx":
        doc = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    raise ValueError(f"Unsupported file type: {ext}")