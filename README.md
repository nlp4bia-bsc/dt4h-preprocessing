# DT4H Preprocessing

Text extraction microservice for the DT4H Cogstack-NiFi pipeline. Receives patient record metadata and a file path, extracts plain text from the record, and returns the original payload with a `text` field appended. Output feeds into OpenSearch (Avro) for downstream NER+NEL annotation.

NiFi sends one flowfile at a time; the service processes each record individually.

## API

### `POST /process`

**Request**
```json
{
  "patient_id": "P001",
  "admission_id": "A123",
  "text_path": "/opt/data/notes/P001.txt",
  "...": "any additional metadata fields are passed through unchanged"
}
```

`contact_id` can be used instead of `admission_id`. Both `patient_id` and one of the two ID fields are required.

**Response `200`**
```json
{
  "patient_id": "P001",
  "admission_id": "A123",
  "text_path": "/opt/data/notes/P001.txt",
  "text": "Extracted plain text content...",
  "...": "..."
}
```

**Response `422`** — returned if validation or extraction fails.
```json
{
  "error": "Validation failed",
  "detail": "admission_id or contact_id required"
}
```

### Supported formats

| Format | Notes |
|--------|-------|
| `.txt` | Encoding auto-detected |
| `.pdf` | All pages extracted |
| `.docx` | Paragraph text joined |
| `.xml` | All text nodes concatenated |
| `.json` | Reads top-level `text` or `Text` key |

## Running

**Local**
```bash
uv sync
uv run uvicorn main:app --reload --port 5002
```

**Docker**
```bash
docker compose up --build
```

The service joins the external `cogstack-net` network and mounts `/opt` from the host so that `text_path` values from NiFi resolve correctly inside the container.

## Testing & validation

### Automated tests

```bash
uv sync
uv run pytest test_api.py -v
```

Covers: attribute validation, all supported file formats, `.txt` encoding variants (UTF-8, Latin-1, CP1252, UTF-16). All 17 tests should pass in under 1 second.

---

### Generating test records

`create_test_records.py` converts a directory of `.txt` files into all supported formats (txt, pdf, xml, docx) and writes ready-to-POST API payloads for each.

```bash
uv run python create_test_records.py
```

**Optional arguments**

| Argument | Default | Description |
|----------|---------|-------------|
| `--source DIR` | `milestones_data` | Directory with language subdirectories containing `.txt` files |
| `--records DIR` | `test_records` | Output root for converted files |
| `--ptrs DIR` | `test_record_ptrs` | Output root for pointer JSONs |
| `--font TTF` | auto-detected | Path to a Unicode TTF font (required for non-ASCII characters in PDFs) |

**Output layout**

```
test_records/{lang}/{format}/{stem}.{ext}
test_record_ptrs/{lang}/{stem}_{ext}.json
```

Each pointer JSON is a complete API payload:
```json
{
  "patient_id": "record_stem",
  "admission_id": "lang_record_stem",
  "text_path": "/absolute/path/to/test_records/lang/format/record_stem.ext"
}
```

Pass a pointer JSON directly to the API:
```bash
curl -s -X POST http://localhost:5002/process \
  -H 'Content-Type: application/json' \
  -d @test_record_ptrs/en/25350173_pdf.json | python3 -m json.tool
```

---

### Manual — start the service first

```bash
uv run uvicorn main:app --reload --port 5002
# or: docker compose up --build
```

---

### curl examples

**Happy path**
```bash
curl -s -X POST http://localhost:5002/process \
  -H 'Content-Type: application/json' \
  -d '{
    "patient_id": "P001",
    "admission_id": "A001",
    "text_path": "/absolute/path/to/file.txt"
  }' | python3 -m json.tool
```
Expected: `200`, response contains `"text": "<extracted content>"`.

---

**Extra metadata fields pass through**
```bash
curl -s -X POST http://localhost:5002/process \
  -H 'Content-Type: application/json' \
  -d '{
    "patient_id": "P001",
    "admission_id": "A001",
    "text_path": "/path/to/file.txt",
    "ward": "Cardiology",
    "source_system": "EPR"
  }' | python3 -m json.tool
```
Expected: `200`, `ward` and `source_system` appear unchanged in the response.

---

### Validation error cases

**Missing `patient_id`** → `422`
```bash
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:5002/process \
  -H 'Content-Type: application/json' \
  -d '{"admission_id": "A001", "text_path": "/path/to/file.txt"}'
```

**Neither `admission_id` nor `contact_id`** → `422`
```bash
curl -s -X POST http://localhost:5002/process \
  -H 'Content-Type: application/json' \
  -d '{"patient_id": "P001", "text_path": "/path/to/file.txt"}' \
  | python3 -m json.tool
```
Expected body: `{"error": "Validation failed", "detail": "admission_id or contact_id required"}`.

**File does not exist** → `422`
```bash
curl -s -X POST http://localhost:5002/process \
  -H 'Content-Type: application/json' \
  -d '{"patient_id": "P001", "admission_id": "A001", "text_path": "/tmp/ghost.txt"}' \
  | python3 -m json.tool
```

**Unsupported format (`.md`, `.csv`, etc.)** → `422`
```bash
curl -s -X POST http://localhost:5002/process \
  -H 'Content-Type: application/json' \
  -d '{"patient_id": "P001", "admission_id": "A001", "text_path": "/path/to/file.csv"}' \
  | python3 -m json.tool
```

---

### What to verify

| Check | Pass condition |
|-------|---------------|
| `200` response has `"text"` key | Non-empty string |
| Extra fields preserved | Exact values match input |
| `422` body has `"detail"` key | Describes the failure reason |

## Known limitations

- `.xml`: extracts all text nodes generically — element-specific extraction (e.g. HL7/CDA) pending stakeholder feedback
- `.json`: only reads top-level `text`/`Text` — nested structures not yet supported
- Encoding values `"No encoding"` / `"Unknown"` handled best-effort via charset-normalizer; edge cases not validated
