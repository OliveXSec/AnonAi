# AnonAI

> **Strip the PII, keep the meaning, get it back afterwards.** AnonAI sits
> between your data and the model: sensitive values leave as stable
> placeholders, the model reasons over text that still reads naturally, and
> the originals are restored in the response.

---

## Overview

**What it does.** AnonAI detects and replaces personally identifiable and
security-sensitive information in text, PDFs, Word documents and scanned images
before that content reaches a language model. Replacement is consistent and
reversible: the same value always becomes the same placeholder, and a mapping
lets you restore the originals once the model has answered.

**How it works.** Two detection layers run in a single pass. Custom regex
recognizers handle structured values where a pattern alone is not enough —
Argentine CUIT/CUIL with mod-11 checksum validation, DNI, credit cards verified
by Luhn, and API keys matched either by known prefix (`sk-`, `ghp_`, `AKIA`,
Slack tokens) or by Shannon entropy for unknown formats. Microsoft Presidio with
a spaCy NER model handles the unstructured half: names, organisations and
locations, which no regex can catch. Overlapping detections are resolved in
favour of the highest-confidence match, then each value is swapped for a typed
placeholder such as `[PERSON_1]` or `[AR_DNI_1]`. The checksum and entropy
validation is what keeps precision usable: a 16-digit order number is not
reported as a credit card, and a low-entropy string is not reported as a secret.

**Why it matters for security teams.** Sending a client's logs, a penetration
test report or a support ticket to a hosted model is a data transfer, and in
many engagements a contractual problem. AnonAI makes that transfer safe by
construction: the model sees structure and language but no identities, no card
numbers and no live credentials. In irreversible mode no mapping is produced at
all, for pipelines where the original values must never be recoverable
downstream.

**Why it matters for organisations.** Teams adopting AI assistants hit the same
wall — the data most worth analysing is the data least permitted to leave. A
sanitisation layer with a defensible detection story turns that from a blocking
compliance question into a reviewable control, and the entity whitelist and
blacklist let a legal or privacy team define exactly what gets scrubbed. The
placeholder mapping means the workflow stays usable end to end: the answer the
model produces comes back carrying real names again.

**Results.** 96% recall against a synthetic ground-truth corpus, with 100%
recall on every regex-backed entity type — CUIT/CUIL, DNI, credit cards, emails
and IP addresses — where the remaining gap is NER missing some unstructured
names. 56 tests cover detection, token consistency, round-trip restoration,
file extraction and a no-leak assertion over the sample corpus. Input formats:
plain text, PDF, DOCX and images via Tesseract OCR, individually or over a whole
directory. The integration suite prints a per-entity recall table, so the
detection rate is a measured number you can re-run, not a claim.

---

## Descripción general

**Qué hace.** AnonAI detecta y reemplaza información personal identificable y
datos sensibles de seguridad en texto, PDFs, documentos Word e imágenes
escaneadas, antes de que ese contenido llegue a un modelo de lenguaje. El
reemplazo es consistente y reversible: un mismo valor siempre se convierte en el
mismo placeholder, y un mapeo permite restaurar los originales una vez que el
modelo respondió.

**Cómo funciona.** Dos capas de detección corren en una sola pasada. Los
recognizers de regex propios cubren los valores estructurados donde el patrón
por sí solo no alcanza: CUIT/CUIL argentino con validación de dígito
verificador módulo 11, DNI, tarjetas de crédito verificadas por Luhn, y API keys
identificadas por prefijo conocido (`sk-`, `ghp_`, `AKIA`, tokens de Slack) o
por entropía de Shannon cuando el formato es desconocido. Microsoft Presidio con
un modelo NER de spaCy cubre la mitad no estructurada: nombres, organizaciones y
ubicaciones, que ninguna expresión regular puede capturar. Las detecciones
solapadas se resuelven a favor de la de mayor confianza y cada valor se
sustituye por un placeholder tipado como `[PERSON_1]` o `[AR_DNI_1]`. Esa
validación por checksum y entropía es lo que mantiene usable la precisión: un
número de pedido de 16 dígitos no se reporta como tarjeta, y una cadena de baja
entropía no se reporta como secreto.

**Para qué sirve a un equipo de seguridad.** Mandar los logs de un cliente, un
reporte de pentest o un ticket de soporte a un modelo alojado es una
transferencia de datos y, en muchos engagements, un problema contractual. AnonAI
vuelve segura esa transferencia por construcción: el modelo ve estructura y
lenguaje, pero no identidades, ni números de tarjeta, ni credenciales vivas. En
modo irreversible no se genera mapeo alguno, para pipelines donde los valores
originales nunca deben poder recuperarse aguas abajo.

**Para qué sirve a una empresa.** Los equipos que adoptan asistentes de IA
chocan siempre contra la misma pared: los datos que más valdría analizar son los
que menos permiso tienen de salir. Una capa de sanitización con una historia de
detección defendible convierte eso, de una pregunta de cumplimiento que bloquea,
en un control auditable; y las listas blanca y negra de entidades permiten que
el área legal o de privacidad defina exactamente qué se anonimiza. El mapeo de
placeholders mantiene el flujo utilizable de punta a punta: la respuesta del
modelo vuelve con los nombres reales.

**Resultados.** 96% de recall contra un corpus sintético de ground truth, con
100% de recall en cada tipo de entidad respaldada por regex —CUIT/CUIL, DNI,
tarjetas, emails e IPs—, donde la diferencia restante es el NER perdiendo
algunos nombres no estructurados. 56 tests cubren detección, consistencia de
tokens, restauración de ida y vuelta, extracción de archivos y una aserción de
no-fuga sobre el corpus de muestra. Formatos de entrada: texto plano, PDF, DOCX
e imágenes vía OCR con Tesseract, de a uno o sobre un directorio completo. La
suite de integración imprime una tabla de recall por entidad, así que la tasa de
detección es un número medible y re-ejecutable, no una afirmación.

---

## Detection layers

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

Requires **Python 3.10-3.13**. `presidio-analyzer` does not publish wheels for
3.14 yet, and the `python3` shipped with macOS is 3.9 -- name the interpreter
explicitly if your default is one of those.

```bash
# Quick setup (creates venv, installs everything, verifies)
# Picks a suitable interpreter and installs Tesseract on macOS or Linux.
./setup.sh

# Or manually
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download es_core_news_lg

# For image OCR (optional)
brew install tesseract tesseract-lang          # macOS
# sudo apt install tesseract-ocr tesseract-ocr-spa   # Debian/Ubuntu
```

Image OCR is the only optional piece: without Tesseract, text, PDF and DOCX
still work.

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
├── requirements.txt    # Pinned runtime dependencies
├── requirements-dev.txt # Test-only dependencies (pytest, reportlab)
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
# The suite needs pytest and reportlab (PDF fixtures) on top of the runtime deps
.venv/bin/pip install -r requirements-dev.txt

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

MIT. See [LICENSE](LICENSE).

## Author

[OliveX Security](https://olivex.io)
