"""Custom Presidio recognizers for Argentine PII and security-sensitive patterns."""

from __future__ import annotations

import math
import re
from typing import Optional

from presidio_analyzer import Pattern, PatternRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts


class CUITRecognizer(PatternRecognizer):
    """Detecta CUIT/CUIL argentino: XX-XXXXXXXX-X."""

    VALID_PREFIXES = {"20", "23", "24", "25", "26", "27", "30", "33", "34"}

    def __init__(self) -> None:
        patterns = [
            Pattern("CUIT", r"\b(\d{2})-(\d{8})-(\d)\b", 0.85),
        ]
        super().__init__(
            supported_entity="AR_CUIT",
            patterns=patterns,
            supported_language="es",
            name="CUITRecognizer",
        )

    def validate_result(self, pattern_text: str) -> Optional[bool]:
        clean = pattern_text.replace("-", "")
        prefix = clean[:2]
        if prefix not in self.VALID_PREFIXES:
            return False
        weights = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
        total = sum(int(d) * w for d, w in zip(clean[:10], weights))
        remainder = total % 11
        expected = {0: 0, 1: 1}.get(remainder, 11 - remainder)
        return int(clean[10]) == expected


class DNIRecognizer(PatternRecognizer):
    """Detecta DNI argentino: 7-8 dígitos."""

    def __init__(self) -> None:
        patterns = [
            Pattern("DNI_labeled", r"\bDNI\s*:?\s*(\d{7,8})\b", 0.9),
            Pattern("DNI_bare", r"\b(\d{7,8})\b", 0.3),
        ]
        super().__init__(
            supported_entity="AR_DNI",
            patterns=patterns,
            supported_language="es",
            name="DNIRecognizer",
        )

    def validate_result(self, pattern_text: str) -> Optional[bool]:
        digits = re.sub(r"\D", "", pattern_text)
        if not (7 <= len(digits) <= 8):
            return False
        n = int(digits)
        return 1_000_000 <= n <= 99_999_999


class CustomEmailRecognizer(PatternRecognizer):
    """Detecta direcciones de email."""

    def __init__(self) -> None:
        patterns = [
            Pattern(
                "EMAIL",
                r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
                0.95,
            ),
        ]
        super().__init__(
            supported_entity="EMAIL_ADDRESS",
            patterns=patterns,
            supported_language="es",
            name="CustomEmailRecognizer",
        )


class IPv4Recognizer(PatternRecognizer):
    """Detecta direcciones IPv4."""

    def __init__(self) -> None:
        patterns = [
            Pattern(
                "IPV4",
                r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b",
                0.85,
            ),
        ]
        super().__init__(
            supported_entity="IP_ADDRESS",
            patterns=patterns,
            supported_language="es",
            name="IPv4Recognizer",
        )


class IPv6Recognizer(PatternRecognizer):
    """Detecta direcciones IPv6."""

    def __init__(self) -> None:
        patterns = [
            Pattern(
                "IPV6",
                r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b",
                0.80,
            ),
            Pattern(
                "IPV6_COMPRESSED",
                r"\b(?:[0-9a-fA-F]{1,4}:){1,7}:\b",
                0.70,
            ),
        ]
        super().__init__(
            supported_entity="IP_ADDRESS",
            patterns=patterns,
            supported_language="es",
            name="IPv6Recognizer",
        )


def _luhn_check(number: str) -> bool:
    digits = [int(d) for d in number]
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        total += sum(divmod(d * 2, 10))
    return total % 10 == 0


class CustomCreditCardRecognizer(PatternRecognizer):
    """Detecta tarjetas de crédito con validación Luhn."""

    def __init__(self) -> None:
        patterns = [
            Pattern(
                "CC_SPACED",
                r"\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b",
                0.6,
            ),
            Pattern(
                "CC_AMEX",
                r"\b(\d{4}[\s\-]?\d{6}[\s\-]?\d{5})\b",
                0.6,
            ),
        ]
        super().__init__(
            supported_entity="CREDIT_CARD",
            patterns=patterns,
            supported_language="es",
            name="CustomCreditCardRecognizer",
        )

    def validate_result(self, pattern_text: str) -> Optional[bool]:
        digits = re.sub(r"[\s\-]", "", pattern_text)
        if not digits.isdigit() or not (13 <= len(digits) <= 19):
            return False
        return _luhn_check(digits)


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    length = len(s)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())


class APIKeyRecognizer(PatternRecognizer):
    """Detecta API keys, secrets y tokens con prefijos conocidos o alta entropía."""

    KNOWN_PREFIXES = re.compile(
        r"\b("
        r"sk-[A-Za-z0-9]{20,}"
        r"|pk-[A-Za-z0-9]{20,}"
        r"|ghp_[A-Za-z0-9]{36,}"
        r"|xox[baprs]-[A-Za-z0-9\-]{10,}"
        r"|AKIA[0-9A-Z]{16}"
        r")\b"
    )

    GENERIC_TOKEN = re.compile(
        r"\b[A-Za-z0-9_\-]{40,}\b"
    )

    ENTROPY_THRESHOLD = 4.0

    def __init__(self) -> None:
        patterns = [Pattern("PLACEHOLDER", r"NEVER_MATCH_PLACEHOLDER", 0.01)]
        super().__init__(
            supported_entity="API_KEY",
            patterns=patterns,
            supported_language="es",
            name="APIKeyRecognizer",
        )

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: Optional[NlpArtifacts] = None,
    ) -> list[RecognizerResult]:
        results: list[RecognizerResult] = []
        for match in self.KNOWN_PREFIXES.finditer(text):
            results.append(
                RecognizerResult(
                    entity_type="API_KEY",
                    start=match.start(),
                    end=match.end(),
                    score=0.95,
                )
            )

        covered = {range(r.start, r.end) for r in results}
        for match in self.GENERIC_TOKEN.finditer(text):
            if any(match.start() in r for r in covered):
                continue
            token = match.group()
            if _shannon_entropy(token) >= self.ENTROPY_THRESHOLD:
                has_upper = bool(re.search(r"[A-Z]", token))
                has_lower = bool(re.search(r"[a-z]", token))
                has_digit = bool(re.search(r"[0-9]", token))
                if sum([has_upper, has_lower, has_digit]) >= 2:
                    results.append(
                        RecognizerResult(
                            entity_type="API_KEY",
                            start=match.start(),
                            end=match.end(),
                            score=0.75,
                        )
                    )
        return results


ALL_RECOGNIZERS: list[type[PatternRecognizer]] = [
    CUITRecognizer,
    DNIRecognizer,
    CustomEmailRecognizer,
    IPv4Recognizer,
    IPv6Recognizer,
    CustomCreditCardRecognizer,
    APIKeyRecognizer,
]
