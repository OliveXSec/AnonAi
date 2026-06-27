"""PII anonymization module with consistent, reversible token replacement.

Combines regex-based pattern detection with Microsoft Presidio + spaCy NER
for comprehensive PII detection in Spanish text.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from presidio_analyzer import AnalyzerEngine, RecognizerResult
    from presidio_analyzer.nlp_engine import NlpEngineProvider
except ImportError:
    print(
        "ERROR: presidio-analyzer no está instalado.\n"
        "  pip install presidio-analyzer\n",
        file=sys.stderr,
    )
    raise

try:
    import spacy

    if not spacy.util.is_package("es_core_news_lg"):
        print(
            "ERROR: modelo de spaCy 'es_core_news_lg' no encontrado.\n"
            "  python -m spacy download es_core_news_lg\n",
            file=sys.stderr,
        )
        sys.exit(1)
except ImportError:
    print(
        "ERROR: spaCy no está instalado.\n"
        "  pip install spacy\n"
        "  python -m spacy download es_core_news_lg\n",
        file=sys.stderr,
    )
    raise

from recognizers import ALL_RECOGNIZERS


@dataclass
class AnonymizeResult:
    """Result of an anonymization pass."""

    text: str
    mapping: Optional[dict[str, str]] = None


@dataclass
class _TokenState:
    counters: dict[str, int] = field(default_factory=dict)
    value_to_token: dict[str, str] = field(default_factory=dict)
    token_to_value: dict[str, str] = field(default_factory=dict)

    def get_or_create(self, entity_type: str, value: str) -> str:
        normalized = value.strip()
        if normalized in self.value_to_token:
            return self.value_to_token[normalized]
        self.counters[entity_type] = self.counters.get(entity_type, 0) + 1
        token = f"[{entity_type}_{self.counters[entity_type]}]"
        self.value_to_token[normalized] = token
        self.token_to_value[token] = normalized
        return token


class Anonymizer:
    """PII anonymizer combining regex patterns and Presidio NER.

    Args:
        reversible: If True, anonymize() returns a mapping that restore() can use.
        score_threshold: Minimum confidence score for Presidio detections.
        entity_whitelist: If set, only detect these entity types.
        entity_blacklist: Entity types to exclude from detection.
    """

    DEFAULT_ENTITIES = [
        "PERSON",
        "LOCATION",
        "ORGANIZATION",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "IP_ADDRESS",
        "CREDIT_CARD",
        "AR_CUIT",
        "AR_DNI",
        "API_KEY",
        "NRP",
        "DATE_TIME",
    ]

    def __init__(
        self,
        reversible: bool = True,
        score_threshold: float = 0.35,
        entity_whitelist: Optional[list[str]] = None,
        entity_blacklist: Optional[list[str]] = None,
    ) -> None:
        self.reversible = reversible
        self.score_threshold = score_threshold
        self.entity_blacklist = set(entity_blacklist or [])

        if entity_whitelist is not None:
            self.entities = [e for e in entity_whitelist if e not in self.entity_blacklist]
        else:
            self.entities = [e for e in self.DEFAULT_ENTITIES if e not in self.entity_blacklist]

        nlp_config = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "es", "model_name": "es_core_news_lg"}],
        }
        provider = NlpEngineProvider(nlp_configuration=nlp_config)
        nlp_engine = provider.create_engine()

        self.analyzer = AnalyzerEngine(
            nlp_engine=nlp_engine,
            supported_languages=["es"],
        )

        for recognizer_cls in ALL_RECOGNIZERS:
            self.analyzer.registry.add_recognizer(recognizer_cls())

    def anonymize(self, text: str) -> AnonymizeResult:
        """Detect and replace PII in text with consistent placeholders.

        Returns AnonymizeResult with sanitized text and (if reversible) the token mapping.
        """
        results = self.analyzer.analyze(
            text=text,
            language="es",
            entities=self.entities,
            score_threshold=self.score_threshold,
        )

        results = self._deduplicate(results)
        results.sort(key=lambda r: r.start)

        token_state = _TokenState()
        output_parts: list[str] = []
        last_end = 0

        for result in results:
            span = text[result.start : result.end]
            leading = len(span) - len(span.lstrip())
            trailing = len(span) - len(span.rstrip())
            start = result.start + leading
            end = result.end - trailing if trailing else result.end
            original = text[start:end]
            token = token_state.get_or_create(result.entity_type, original)
            output_parts.append(text[last_end:start])
            output_parts.append(token)
            last_end = end

        output_parts.append(text[last_end:])
        sanitized = "".join(output_parts)

        mapping = dict(token_state.token_to_value) if self.reversible else None
        return AnonymizeResult(text=sanitized, mapping=mapping)

    def anonymize_file(self, path: str | Path, **kwargs) -> AnonymizeResult:
        """Extract text from a file and anonymize it.

        Supports: .pdf, .docx, .png, .jpg, .jpeg, .tiff, .bmp, .webp, .txt
        Extra kwargs are passed to the reader (e.g. pages=[0,1] for PDF, lang='eng' for OCR).
        """
        from readers import read_file

        text = read_file(path, **kwargs)
        return self.anonymize(text)

    def anonymize_directory(
        self,
        directory: str | Path,
        extensions: Optional[list[str]] = None,
        recursive: bool = False,
        **kwargs,
    ) -> dict[str, AnonymizeResult]:
        """Anonymize all supported files in a directory.

        Returns dict mapping file path to AnonymizeResult.
        """
        from readers import read_directory

        texts = read_directory(directory, extensions=extensions, recursive=recursive, **kwargs)
        results: dict[str, AnonymizeResult] = {}
        for file_path, text in texts.items():
            if text.startswith("[ERROR:"):
                results[file_path] = AnonymizeResult(text=text, mapping=None)
            else:
                results[file_path] = self.anonymize(text)
        return results

    @staticmethod
    def restore(text: str, mapping: dict[str, str]) -> str:
        """Replace placeholders in text with original values using the mapping."""
        result = text
        for token, original in sorted(mapping.items(), key=lambda x: -len(x[0])):
            result = result.replace(token, original)
        return result

    @staticmethod
    def _deduplicate(results: list[RecognizerResult]) -> list[RecognizerResult]:
        """Remove overlapping detections, keeping highest-scoring ones."""
        if not results:
            return []
        results.sort(key=lambda r: (-r.score, r.start))
        kept: list[RecognizerResult] = []
        for candidate in results:
            overlaps = False
            for existing in kept:
                if candidate.start < existing.end and candidate.end > existing.start:
                    overlaps = True
                    break
            if not overlaps:
                kept.append(candidate)
        return kept
