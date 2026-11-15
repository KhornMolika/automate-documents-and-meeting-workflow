import io
import hashlib
from typing import Tuple
from pypdf import PdfReader
import docx
import openpyxl


def compute_sha256(file_bytes: bytes) -> str:
    """Computes SHA-256 checksum for document deduplication."""
    return hashlib.sha256(file_bytes).hexdigest()


def extract_text(file_bytes: bytes, filename: str) -> str:
    """
    Extracts raw text content from PDF, DOCX, and XLSX files.
    """
    lower_name = filename.lower()
    text_content = []

    try:
        if lower_name.endswith(".pdf"):
            reader = PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_content.append(page_text)

        elif lower_name.endswith(".docx"):
            doc = docx.Document(io.BytesIO(file_bytes))
            for para in doc.paragraphs:
                if para.text.strip():
                    text_content.append(para.text)
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                    if row_text:
                        text_content.append(row_text)

        elif lower_name.endswith(".xlsx"):
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    row_vals = [str(val).strip() for val in row if val is not None]
                    if row_vals:
                        text_content.append(" | ".join(row_vals))

        else:
            # Fallback for plain text or csv
            text_content.append(file_bytes.decode("utf-8", errors="ignore"))

    except Exception as e:
        text_content.append(f"[Extraction warning for {filename}: {str(e)}]")

    return "\n\n".join(text_content)
