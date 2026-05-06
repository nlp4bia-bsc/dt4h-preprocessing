import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

SAMPLE_FILES = Path(__file__).parent / "parsing_test_files"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def post(text_path, **overrides):
    record = {
        "patient_id": "p001",
        "admission_id": "a001",
        "text_path": str(text_path),
        **overrides,
    }
    return client.post("/process", json=record)


def write_encoded(text: str, encoding: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
    tmp.write(text.encode(encoding))
    tmp.close()
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# 1. Attribute validation
# ---------------------------------------------------------------------------

def test_missing_patient_id():
    r = client.post("/process", json={
        "admission_id": "a1", "text_path": str(SAMPLE_FILES / "sample.txt")
    })
    assert r.status_code == 422

def test_missing_both_admission_and_contact_id():
    r = client.post("/process", json={
        "patient_id": "p1", "text_path": str(SAMPLE_FILES / "sample.txt")
    })
    assert r.status_code == 422

def test_admission_id_alone_accepted():
    r = post(SAMPLE_FILES / "sample.txt")
    assert r.status_code == 200

def test_contact_id_alone_accepted():
    r = client.post("/process", json={
        "patient_id": "p1", "contact_id": "c1", "text_path": str(SAMPLE_FILES / "sample.txt")
    })
    assert r.status_code == 200

def test_missing_text_path_field():
    r = client.post("/process", json={"patient_id": "p1", "admission_id": "a1"})
    assert r.status_code == 422

def test_nonexistent_text_path():
    r = post("/tmp/__no_such_file_xyz__.txt")
    assert r.status_code == 422
    assert "detail" in r.json()

def test_extra_fields_pass_through():
    r = client.post("/process", json={
        "patient_id": "p1", "admission_id": "a1",
        "text_path": str(SAMPLE_FILES / "sample.txt"),
        "custom_field": "hello", "ward": 42,
    })
    assert r.status_code == 200
    rec = r.json()
    assert rec["custom_field"] == "hello"
    assert rec["ward"] == 42


# ---------------------------------------------------------------------------
# 2. File type extraction
# ---------------------------------------------------------------------------

def test_txt_extraction():
    r = post(SAMPLE_FILES / "sample.txt")
    assert r.status_code == 200
    assert "plain text" in r.json()["text"]

def test_pdf_extraction():
    r = post(SAMPLE_FILES / "sample.pdf")
    assert r.status_code == 200
    assert len(r.json()["text"]) > 0

def test_docx_extraction():
    r = post(SAMPLE_FILES / "sample.docx")
    assert r.status_code == 200
    assert len(r.json()["text"]) > 0

def test_xml_extraction():
    r = post(SAMPLE_FILES / "sample.xml")
    assert r.status_code == 200
    text = r.json()["text"]
    assert "Hello" in text and "World" in text

def test_unsupported_md_returns_422():
    r = post(SAMPLE_FILES / "sample.md")
    assert r.status_code == 422
    assert "detail" in r.json()

def test_text_key_added_to_output():
    r = post(SAMPLE_FILES / "sample.txt")
    assert r.status_code == 200
    assert "text" in r.json()


# ---------------------------------------------------------------------------
# 3. Encoding variants for .txt
# ---------------------------------------------------------------------------

ENCODING_SAMPLE = "Café résumé naïve"  # chars valid in utf-8, latin-1, cp1252, utf-16

@pytest.mark.parametrize("encoding", ["utf-8", "latin-1", "cp1252", "utf-16"])
def test_txt_encoding(encoding):
    path = write_encoded(ENCODING_SAMPLE, encoding)
    try:
        r = post(path)
        assert r.status_code == 200, f"encoding={encoding} → {r.json()}"
        text = r.json()["text"]
        assert len(text) > 0
        # charset_normalizer should recover the readable text
        assert "Caf" in text
    finally:
        path.unlink(missing_ok=True)
