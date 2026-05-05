import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pdfplumber
from docx import Document

from encoding import detect_and_read


def extract_text(path_str: str) -> str:
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"text_path not found: {path_str}")

    suffix = path.suffix.lower().lstrip('.')

    match suffix:
        case 'txt':
            return detect_and_read(path)
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
