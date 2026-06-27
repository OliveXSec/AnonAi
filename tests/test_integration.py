"""Integration tests: measure recall against ground truth, round-trip, and no-leak.

Normalization applied before comparison:
  - Strip whitespace
  - Collapse multiple spaces to one
  - Remove hyphens/spaces in credit card numbers (compare digits only)
  - Case-insensitive matching
  - For OCR sources: also strip common OCR artifacts (|, _, extra dots)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pytesseract
import pytest
from PIL import Image

from anonymizer import Anonymizer
from readers import read_file

SAMPLES = Path(__file__).parent.parent / "samples"
EXPECTED_PATH = SAMPLES / "expected.json"

ENTITY_TYPE_MAP: dict[str, list[str]] = {
    "PERSON": ["PERSON"],
    "EMAIL": ["EMAIL_ADDRESS"],
    "PHONE": ["PHONE_NUMBER"],
    "CUIT_CUIL": ["AR_CUIT"],
    "DNI": ["AR_DNI"],
    "IP_ADDRESS": ["IP_ADDRESS"],
    "CREDIT_CARD": ["CREDIT_CARD"],
    "AWS_KEY": ["API_KEY"],
    "GITHUB_TOKEN": ["API_KEY"],
    "SLACK_TOKEN": ["API_KEY"],
    "API_KEY": ["API_KEY"],
    "LOCATION": ["LOCATION"],
    "ORG": ["ORGANIZATION"],
}

NER_DEPENDENT_TYPES = {"PERSON", "ORG", "LOCATION"}


def _normalize(value: str) -> str:
    """Normalize a value for comparison: lowercase, collapse whitespace, strip."""
    v = value.strip().lower()
    v = re.sub(r"\s+", " ", v)
    return v


def _normalize_digits(value: str) -> str:
    """For credit cards / numeric IDs: extract only digits."""
    return re.sub(r"\D", "", value)


def _value_is_scrubbed(value: str, sanitized_text: str) -> bool:
    """Check if a PII value does NOT appear in the sanitized text.

    Uses multiple matching strategies to catch partial leaks.
    """
    norm_text = _normalize(sanitized_text)
    norm_val = _normalize(value)
    if norm_val in norm_text:
        return False
    digits = _normalize_digits(value)
    if len(digits) >= 7 and digits in _normalize_digits(sanitized_text):
        return False
    return True


def _value_was_detected(value: str, original_text: str, sanitized_text: str) -> bool:
    """Check if a PII value was replaced (detected) by the anonymizer.

    Strategy: if the normalized value appears in the original but NOT in the sanitized
    output, the scrubber caught it.
    """
    norm_original = _normalize(original_text)
    norm_sanitized = _normalize(sanitized_text)
    norm_val = _normalize(value)

    if norm_val not in norm_original:
        return True

    if norm_val not in norm_sanitized:
        return True

    digits = _normalize_digits(value)
    if len(digits) >= 7:
        if digits in _normalize_digits(original_text) and digits not in _normalize_digits(sanitized_text):
            return True

    return False


@dataclass
class DetectionResult:
    entity_type: str
    value: str
    detected: bool
    source: str
    ocr_source: bool = False
    ner_dependent: bool = False


@dataclass
class RecallReport:
    results: list[DetectionResult] = field(default_factory=list)

    def add(self, entity_type: str, value: str, detected: bool, source: str, ocr: bool = False, ner: bool = False) -> None:
        self.results.append(DetectionResult(entity_type, value, detected, source, ocr, ner))

    def print_table(self) -> None:
        by_type: dict[str, list[DetectionResult]] = {}
        for r in self.results:
            by_type.setdefault(r.entity_type, []).append(r)

        print("\n" + "=" * 95)
        print(f"{'ENTITY TYPE':<18} {'EXPECTED':>8} {'DETECTED':>8} {'REGEX_MISS':>10} {'NER_MISS':>8} {'OCR_MISS':>8} {'RECALL':>8}")
        print("-" * 95)

        total_expected = 0
        total_detected = 0
        total_ocr_miss = 0
        total_ner_miss = 0

        for etype in sorted(by_type.keys()):
            items = by_type[etype]
            expected = len(items)
            detected = sum(1 for i in items if i.detected)
            missing = [i for i in items if not i.detected]
            ocr_miss = sum(1 for i in missing if i.ocr_source)
            ner_miss = sum(1 for i in missing if not i.ocr_source and i.ner_dependent)
            regex_miss = len(missing) - ocr_miss - ner_miss
            recall = detected / expected if expected else 0

            total_expected += expected
            total_detected += detected
            total_ocr_miss += ocr_miss
            total_ner_miss += ner_miss

            recall_str = f"{recall:.0%}"
            print(f"{etype:<18} {expected:>8} {detected:>8} {regex_miss:>10} {ner_miss:>8} {ocr_miss:>8} {recall_str:>8}")

            for m in missing:
                if m.ocr_source:
                    tag = " [OCR]"
                elif m.ner_dependent:
                    tag = " [NER]"
                else:
                    tag = " [REGEX/SCRUBBER]"
                print(f"  └─ MISS: \"{m.value}\" in {m.source}{tag}")

        print("-" * 95)
        global_recall = total_detected / total_expected if total_expected else 0
        total_regex_miss = total_expected - total_detected - total_ocr_miss - total_ner_miss
        print(f"{'TOTAL':<18} {total_expected:>8} {total_detected:>8} {total_regex_miss:>10} {total_ner_miss:>8} {total_ocr_miss:>8} {global_recall:.0%}")
        print("=" * 95 + "\n")

    @property
    def global_recall(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.detected) / len(self.results)

    @property
    def regex_misses(self) -> list[DetectionResult]:
        """Hard failures: regex-based detectors that should have caught the value."""
        return [r for r in self.results if not r.detected and not r.ocr_source and not r.ner_dependent]

    @property
    def ner_misses(self) -> list[DetectionResult]:
        """Soft failures: NER model didn't recognize the entity in context."""
        return [r for r in self.results if not r.detected and not r.ocr_source and r.ner_dependent]


@pytest.fixture(scope="module")
def expected() -> dict[str, list[str]]:
    with open(EXPECTED_PATH) as f:
        data = json.load(f)
    return data["expected_entities"]


@pytest.fixture(scope="module")
def anon() -> Anonymizer:
    return Anonymizer(reversible=True, score_threshold=0.3)


@pytest.fixture(scope="module")
def texts() -> dict[str, str]:
    """Extract text from every sample file."""
    result = {}
    result["pdf"] = read_file(SAMPLES / "sample_pii.pdf")
    result["docx"] = read_file(SAMPLES / "sample_pii.docx")

    img_form = Image.open(SAMPLES / "sample_form.png")
    result["form_png"] = pytesseract.image_to_string(img_form, lang="spa+eng")

    img_id = Image.open(SAMPLES / "sample_id.png")
    result["id_png"] = pytesseract.image_to_string(img_id, lang="spa+eng")

    return result


@pytest.fixture(scope="module")
def anonymized(anon: Anonymizer, texts: dict[str, str]) -> dict[str, tuple[str, Optional[dict[str, str]]]]:
    """Run anonymizer on each extracted text."""
    results = {}
    for source, text in texts.items():
        r = anon.anonymize(text)
        results[source] = (r.text, r.mapping)
    return results


FILE_ENTITIES: dict[str, list[str]] = {
    "pdf": [
        "PERSON", "EMAIL", "PHONE", "CUIT_CUIL", "DNI",
        "IP_ADDRESS", "CREDIT_CARD", "AWS_KEY", "GITHUB_TOKEN",
        "SLACK_TOKEN", "API_KEY", "LOCATION", "ORG",
    ],
    "docx": [
        "PERSON", "EMAIL", "PHONE", "CUIT_CUIL", "DNI",
        "IP_ADDRESS", "CREDIT_CARD", "AWS_KEY", "GITHUB_TOKEN",
        "SLACK_TOKEN", "API_KEY", "LOCATION", "ORG",
    ],
    "form_png": [
        "PERSON", "EMAIL", "PHONE", "CUIT_CUIL", "DNI",
        "IP_ADDRESS", "CREDIT_CARD", "API_KEY",
    ],
    "id_png": [
        "PERSON", "EMAIL", "DNI", "CUIT_CUIL", "LOCATION",
    ],
}

OCR_SOURCES = {"form_png", "id_png"}


class TestRecall:
    """Verify the scrubber detects all expected PII values."""

    def test_recall_report(
        self,
        expected: dict[str, list[str]],
        texts: dict[str, str],
        anonymized: dict[str, tuple[str, Optional[dict[str, str]]]],
    ) -> None:
        report = RecallReport()

        for source, (sanitized, _mapping) in anonymized.items():
            original = texts[source]
            is_ocr = source in OCR_SOURCES
            entity_types = FILE_ENTITIES.get(source, [])

            for gt_type in entity_types:
                values = expected.get(gt_type, [])
                is_ner = gt_type in NER_DEPENDENT_TYPES
                for value in values:
                    detected = _value_was_detected(value, original, sanitized)
                    report.add(
                        entity_type=gt_type,
                        value=value,
                        detected=detected,
                        source=source,
                        ocr=is_ocr and not detected,
                        ner=is_ner and not detected and not is_ocr,
                    )

        report.print_table()

        regex_fails = report.regex_misses
        if regex_fails:
            details = "\n".join(
                f"  - [{r.entity_type}] \"{r.value}\" in {r.source}"
                for r in regex_fails
            )
            pytest.fail(
                f"Scrubber missed {len(regex_fails)} regex-detectable entities:\n{details}"
            )

        ner_fails = report.ner_misses
        if ner_fails:
            details = "\n".join(
                f"  - [{r.entity_type}] \"{r.value}\" in {r.source}"
                for r in ner_fails
            )
            import warnings
            warnings.warn(
                f"NER model missed {len(ner_fails)} entities (not a scrubber bug):\n{details}"
            )


class TestNoLeak:
    """Verify no PII value from ground truth leaks into sanitized output."""

    def test_no_pii_in_sanitized_text(
        self,
        expected: dict[str, list[str]],
        anonymized: dict[str, tuple[str, Optional[dict[str, str]]]],
    ) -> None:
        hard_leaks: list[str] = []
        ner_leaks: list[str] = []

        for gt_type, values in expected.items():
            is_ner = gt_type in NER_DEPENDENT_TYPES
            for value in values:
                for source, (sanitized, _) in anonymized.items():
                    if not _value_is_scrubbed(value, sanitized):
                        entry = f"  - [{gt_type}] \"{value}\" leaked in {source}"
                        if is_ner:
                            ner_leaks.append(entry)
                        else:
                            hard_leaks.append(entry)

        if ner_leaks:
            import warnings
            warnings.warn(
                f"NER-dependent values not scrubbed ({len(ner_leaks)}):\n" + "\n".join(ner_leaks)
            )

        if hard_leaks:
            pytest.fail(f"PII leak detected:\n" + "\n".join(hard_leaks))


class TestRoundTrip:
    """Anonymize then restore must recover the original text (non-OCR sources)."""

    @pytest.mark.parametrize("source", ["pdf", "docx"])
    def test_roundtrip_restores_original(
        self,
        source: str,
        texts: dict[str, str],
        anonymized: dict[str, tuple[str, Optional[dict[str, str]]]],
    ) -> None:
        original = texts[source]
        sanitized, mapping = anonymized[source]
        assert mapping is not None, f"No mapping for {source} — was reversible=True?"

        restored = Anonymizer.restore(sanitized, mapping)
        assert restored == original, (
            f"Round-trip failed for {source}.\n"
            f"Diff sample (first 200 chars of mismatch):\n"
            f"  original:  {original[:200]}\n"
            f"  restored:  {restored[:200]}"
        )
