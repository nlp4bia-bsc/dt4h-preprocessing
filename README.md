# DT4H Preprocessing

Text extraction microservice for the DT4H Cogstack-NiFi pipeline. Receives patient record metadata and a file path, extracts plain text from the record, and returns the original payload with a `text` field appended. Output feeds into OpenSearch (Avro) for downstream NER+NEL annotation.

## API

### `POST /process_bulk`

**Request**
```json
{
  "content": [
    {
      "patient_id": "P001",
      "admission_id": "A123",
      "text_path": "/opt/cogstack/data/notes/P001.txt",
      "...": "any additional metadata fields are passed through unchanged"
    }
  ]
}
```

`contact_id` can be used instead of `admission_id`. Both `patient_id` and one of the two ID fields are required.

**Response `200`**
```json
{
  "content": [
    {
      "patient_id": "P001",
      "admission_id": "A123",
      "text_path": "/opt/cogstack/data/notes/P001.txt",
      "text": "Extracted plain text content...",
      "...": "..."
    }
  ]
}
```

**Response `422`** — returned if any record fails validation or extraction. The entire batch is rejected.
```json
{
  "error": "Validation failed",
  "failures": [
    { "index": 0, "patient_id": "P001", "detail": "text_path not found: /opt/..." }
  ]
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

## Known limitations

- `.xml`: extracts all text nodes generically — element-specific extraction (e.g. HL7/CDA) pending stakeholder feedback
- `.json`: only reads top-level `text`/`Text` — nested structures not yet supported
- Encoding values `"No encoding"` / `"Unknown"` handled best-effort via charset-normalizer; edge cases not validated
