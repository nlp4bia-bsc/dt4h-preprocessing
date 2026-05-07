import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pdfplumber
from charset_normalizer import from_path
from docx import Document
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator


# ── Models ────────────────────────────────────────────────────────────────────

class RecordInput(BaseModel):
    model_config = ConfigDict(extra='allow')

    patient_id: str
    text_path: str
    admission_id: str | None = None
    contact_id: str | None = None

    @model_validator(mode='after')
    def require_contact_or_admission(self):
        if self.admission_id is None and self.contact_id is None:
            raise ValueError('admission_id or contact_id required')
        return self


# ── Text extraction ───────────────────────────────────────────────────────────

def extract_text(path_str: str) -> str:
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"text_path not found: {path_str}")

    suffix = path.suffix.lower().lstrip('.')

    match suffix:
        case 'txt':
            return _extract_txt(path)
        case 'pdf':
            return _extract_pdf(path)
        case 'docx':
            return _extract_docx(path)
        case 'xml':
            return _extract_xml(path)
        case 'json':
            return _extract_json(path)
        case _:
            raise ValueError(f"Unsupported format: .{suffix}")


def _extract_txt(path: Path) -> str:
    result = from_path(path).best()
    if result is None:
        raise ValueError(f"Could not detect encoding: {path}")
    return str(result)


def _extract_pdf(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        pages = [page.extract_text() or '' for page in pdf.pages]
    return '\n'.join(pages).strip()


def _extract_docx(path: Path) -> str:
    doc = Document(path)
    return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_xml(path: Path) -> str:
    tree = ET.parse(path)
    return ' '.join(tree.getroot().itertext()).strip()


def _extract_json(path: Path) -> str:
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    text = data.get('text') or data.get('Text')
    if text is None:
        raise ValueError("JSON record missing 'text'/'Text' key")
    return str(text)


# ── API ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="DT4H Preprocessing", version="0.1.0")


@app.post("/process")
async def process(request: Request):
    body = await request.json()

    try:
        record = RecordInput.model_validate(body)
    except ValidationError as e:
        return JSONResponse(
            {"error": "Validation failed", "detail": e.errors()[0]["msg"]},
            status_code=422,
        )

    try:
        text = extract_text(record.text_path)
    except Exception as e:
        return JSONResponse(
            {"error": "Extraction failed", "detail": str(e)},
            status_code=422,
        )

    return JSONResponse(record.model_dump() | {"text": text})
