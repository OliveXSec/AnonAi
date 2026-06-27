# AnonAI

PII anonymization module for sanitizing text before sending it to an LLM. Designed as a drop-in layer for security-sensitive AI pipelines.

Combines two detection layers in a single pass:
1. **Custom regex recognizers** for structured patterns (Argentine IDs, credit cards with Luhn validation, API keys with entropy scoring)
2. **Microsoft Presidio + spaCy NER** (`es_core_news_lg`) for unstructured entities (names, organizations, locations)

## How it works

```
Raw text / PDF / DOCX / Image
        |
        v
  +-----------+     +----------------+
  |  Readers   |---->|  Text extraction|  (pdfplumber, python-docx, Tesseract OCR)
  +-----------+     +----------------+
                           |
                           v
                  +------------------+
                  |  Presidio Engine  |
                  |  +--------------+|
                  |  | Custom regex  ||  CUIT, DNI, CC, API keys, IPs, emails
                  |  +--------------+|
                  |  | spaCy NER    ||  PERSON, ORG, LOCATION
                  |  +--------------+|
                  +------------------+
                           |
                           v
                  +------------------+
                  | Token replacement |  Consistent: same value -> same [TYPE_N]
                  | + Deduplication   |  Overlaps resolved by highest score
                  +------------------+
                           |
                    +------+------+
                    |             |
                    v             v
            Sanitized text    Mapping (optional)
            (to the LLM)     {[TYPE_N]: original}
                                  |
                                  v
                          +-------------+
                          |  restore()  |  Revert tokens in LLM response
                          +-------------+
```

### Token consistency

The same original value always maps to the same placeholder throughout the text:

```
"Juan Perez"  -> [PERSON_1]  (every occurrence)
"Maria Lopez" -> [PERSON_2]
"user@test.com" -> [EMAIL_ADDRESS_1]
```

### Reversibility

- **Reversible mode** (default): `anonymize()` returns a mapping `{token: original_value}`. After the LLM responds with placeholders, `restore()` swaps them back.
- **Irreversible mode**: No mapping is generated. The original values are gone. Use when data must never leave the pipeline.

## Installation

```bash
# Quick setup (creates venv, installs everything, verifies)
./setup.sh

# Or manually
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download es_core_news_lg

# For image OCR (optional)
brew install tesseract tesseract-lang   # macOS
# apt install tesseract-ocr tesseract-ocr-spa  # Linux
```

## Usage

### Text

```python
from anonymizer import Anonymizer

anon = Anonymizer(reversible=True)

result = anon.anonymize("Juan Perez, DNI 35123456, email juan@empresa.com")
print(result.text)
# [PERSON_1], DNI [AR_DNI_1], email [EMAIL_ADDRESS_1]

print(result.mapping)
# {'[PERSON_1]': 'Juan Perez', '[AR_DNI_1]': '35123456', '[EMAIL_ADDRESS_1]': 'juan@empresa.com'}

# After LLM responds with placeholders, restore original values
llm_response = "Updated record for [PERSON_1]."
print(Anonymizer.restore(llm_response, result.mapping))
# Updated record for Juan Perez.
```

### Files (PDF, DOCX, images, TXT)

```python
result = anon.anonymize_file("contract.pdf")
result = anon.anonymize_file("report.docx")
result = anon.anonymize_file("scan.png", lang="spa")       # OCR with Tesseract
result = anon.anonymize_file("data.pdf", pages=[0, 2])     # specific pages
```

### Batch (directory)

```python
results = anon.anonymize_directory("./documents/", recursive=True)
results = anon.anonymize_directory("./docs/", extensions=[".pdf", ".docx"])

for path, res in results.items():
    print(f"{path}: {res.text[:100]}...")
```

### Irreversible mode

```python
anon = Anonymizer(reversible=False)
result = anon.anonymize(text)
# result.mapping is None
```

### Filter entities

```python
# Only detect emails and IPs
anon = Anonymizer(entity_whitelist=["EMAIL_ADDRESS", "IP_ADDRESS"])

# Detect everything except names
anon = Anonymizer(entity_blacklist=["PERSON"])
```

### Adjust sensitivity

```python
# Higher threshold = fewer false positives, may miss borderline detections
anon = Anonymizer(score_threshold=0.7)
```

## Supported entities

| Type | Source | Description |
|------|--------|-------------|
| `PERSON` | spaCy NER | Person names |
| `ORGANIZATION` | spaCy NER | Organizations |
| `LOCATION` | spaCy NER | Locations |
| `AR_CUIT` | Regex | Argentine CUIT/CUIL (mod 11 checksum validation) |
| `AR_DNI` | Regex | Argentine DNI (7-8 digits) |
| `EMAIL_ADDRESS` | Regex | Email addresses |
| `IP_ADDRESS` | Regex | IPv4 and IPv6 |
| `CREDIT_CARD` | Regex | Credit cards (Luhn validation to reduce false positives) |
| `API_KEY` | Regex + Entropy | API keys, secrets, tokens (known prefixes + Shannon entropy for generic tokens) |
| `PHONE_NUMBER` | Presidio | Phone numbers |

### API key detection

Detects tokens with known prefixes:
- `sk-` (OpenAI)
- `pk-` (public keys)
- `ghp_` (GitHub PAT)
- `xox[baprs]-` (Slack)
- `AKIA` (AWS access key)

For unknown prefixes, flags high-entropy strings (40+ chars, Shannon entropy >= 4.0, mixed character classes).

## Supported file formats

| Format | Extensions | Dependency | Notes |
|--------|-----------|------------|-------|
| Plain text | `.txt` | (none) | UTF-8 |
| PDF | `.pdf` | pdfplumber | Page selection supported |
| Word | `.docx` | python-docx | Extracts paragraph text and table content |
| Images | `.png`, `.jpg`, `.tiff`, `.bmp`, `.webp` | pytesseract + Pillow | Requires Tesseract installed on the system |

## Project structure

```
.
├── anonymizer.py       # Anonymizer class: anonymize(), anonymize_file(), restore()
├── recognizers.py      # 7 custom Presidio recognizers (CUIT, DNI, CC, API keys, etc.)
├── readers.py          # File text extraction (PDF, DOCX, images, TXT, directories)
├── setup.sh            # One-command installation script
├── requirements.txt    # Pinned dependencies
├── samples/            # Synthetic test data for integration tests
│   ├── expected.json   # Ground truth: entities the scrubber must detect
│   ├── sample_pii.pdf
│   ├── sample_pii.docx
│   ├── sample_form.png
│   └── sample_id.png
└── tests/
    ├── test_anonymizer.py    # Unit tests: detection, consistency, round-trip, config
    ├── test_recognizers.py   # Unit tests: each custom detector
    ├── test_readers.py       # Unit tests: file extraction and anonymize_file()
    └── test_integration.py   # Integration: recall vs ground truth, no-leak, round-trip
```

## Tests

```bash
# Run all tests (56 tests)
.venv/bin/python -m pytest tests/ -v

# Integration tests only (with recall report table)
.venv/bin/python -m pytest tests/test_integration.py -v -s
```

Integration test output includes a recall report:

```
ENTITY TYPE        EXPECTED DETECTED REGEX_MISS NER_MISS OCR_MISS   RECALL
-----------------------------------------------------------------------------------------------
CREDIT_CARD               9        9          0        0        0     100%
CUIT_CUIL                12       12          0        0        0     100%
DNI                       8        8          0        0        0     100%
EMAIL                     8        8          0        0        0     100%
IP_ADDRESS                6        6          0        0        0     100%
...
-----------------------------------------------------------------------------------------------
TOTAL                    79       76          0        3        0      96%
```

## License

MIT

## Author

[OliveX Security](https://olivex.io)
