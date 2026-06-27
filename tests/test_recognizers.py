"""Tests for custom Presidio recognizers."""

import pytest

from recognizers import (
    APIKeyRecognizer,
    CustomCreditCardRecognizer,
    CUITRecognizer,
    DNIRecognizer,
    CustomEmailRecognizer,
    IPv4Recognizer,
    IPv6Recognizer,
    _luhn_check,
    _shannon_entropy,
)


class TestCUITRecognizer:
    def setup_method(self) -> None:
        self.recognizer = CUITRecognizer()

    def test_valid_cuit(self) -> None:
        results = self.recognizer.analyze("CUIT: 20-12345678-6", None, None)
        assert len(results) == 1
        assert results[0].entity_type == "AR_CUIT"

    def test_invalid_prefix(self) -> None:
        assert self.recognizer.validate_result("99-12345678-0") is False

    def test_invalid_checksum(self) -> None:
        assert self.recognizer.validate_result("20-12345678-9") is False


class TestDNIRecognizer:
    def setup_method(self) -> None:
        self.recognizer = DNIRecognizer()

    def test_labeled_dni(self) -> None:
        results = self.recognizer.analyze("DNI: 35123456", None, None)
        assert len(results) >= 1
        labeled = [r for r in results if r.score >= 0.9]
        assert len(labeled) == 1

    def test_dni_too_short(self) -> None:
        assert self.recognizer.validate_result("12345") is False

    def test_valid_range(self) -> None:
        assert self.recognizer.validate_result("35123456") is True
        assert self.recognizer.validate_result("1234567") is True

    def test_below_range(self) -> None:
        assert self.recognizer.validate_result("0000001") is False


class TestCustomEmailRecognizer:
    def setup_method(self) -> None:
        self.recognizer = CustomEmailRecognizer()

    def test_standard_email(self) -> None:
        results = self.recognizer.analyze("contacto: user@example.com fin", None, None)
        assert len(results) == 1
        assert results[0].entity_type == "EMAIL_ADDRESS"

    def test_no_match_on_partial(self) -> None:
        results = self.recognizer.analyze("user@", None, None)
        assert len(results) == 0


class TestIPv4Recognizer:
    def setup_method(self) -> None:
        self.recognizer = IPv4Recognizer()

    def test_valid_ipv4(self) -> None:
        results = self.recognizer.analyze("server en 192.168.1.100 puerto 22", None, None)
        assert len(results) == 1

    def test_invalid_octets(self) -> None:
        results = self.recognizer.analyze("999.999.999.999", None, None)
        assert len(results) == 0


class TestIPv6Recognizer:
    def setup_method(self) -> None:
        self.recognizer = IPv6Recognizer()

    def test_full_ipv6(self) -> None:
        results = self.recognizer.analyze(
            "addr: 2001:0db8:85a3:0000:0000:8a2e:0370:7334", None, None
        )
        assert len(results) == 1


class TestCustomCreditCardRecognizer:
    def setup_method(self) -> None:
        self.recognizer = CustomCreditCardRecognizer()

    def test_luhn_helper(self) -> None:
        assert _luhn_check("4532015112830366") is True
        assert _luhn_check("4532015112830367") is False

    def test_valid_visa(self) -> None:
        results = self.recognizer.analyze("tarjeta 4532 0151 1283 0366", None, None)
        valid = [r for r in results if self.recognizer.validate_result("4532 0151 1283 0366")]
        assert len(valid) >= 1

    def test_invalid_luhn(self) -> None:
        assert self.recognizer.validate_result("1234 5678 9012 3456") is False


class TestAPIKeyRecognizer:
    def setup_method(self) -> None:
        self.recognizer = APIKeyRecognizer()

    def test_sk_prefix(self) -> None:
        results = self.recognizer.analyze(
            "key: sk-abcdefghijklmnopqrstuvwx", None, None
        )
        assert len(results) == 1
        assert results[0].score >= 0.9

    def test_ghp_prefix(self) -> None:
        results = self.recognizer.analyze(
            "token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij", None, None
        )
        assert len(results) == 1

    def test_aws_key(self) -> None:
        results = self.recognizer.analyze("AKIAIOSFODNN7EXAMPLE", None, None)
        assert len(results) == 1

    def test_high_entropy_generic(self) -> None:
        token = "aB3dE5gH7jK9mN1pQ3sT5vX7zA9cE1gI3kM5oQ7sU"
        results = self.recognizer.analyze(f"secret: {token}", None, None)
        assert len(results) >= 1

    def test_low_entropy_skipped(self) -> None:
        results = self.recognizer.analyze(
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", None, None
        )
        assert len(results) == 0

    def test_shannon_entropy(self) -> None:
        assert _shannon_entropy("") == 0.0
        assert _shannon_entropy("aaaa") == 0.0
        assert _shannon_entropy("ab") > 0.9
