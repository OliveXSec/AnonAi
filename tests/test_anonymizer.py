"""Tests for the Anonymizer class: detection, consistency, and round-trip."""

import pytest

from anonymizer import Anonymizer, AnonymizeResult


@pytest.fixture(scope="module")
def anon() -> Anonymizer:
    return Anonymizer(reversible=True, score_threshold=0.35)


@pytest.fixture(scope="module")
def anon_irreversible() -> Anonymizer:
    return Anonymizer(reversible=False)


class TestAnonymize:
    def test_email_detection(self, anon: Anonymizer) -> None:
        result = anon.anonymize("Contactar a user@example.com para más info.")
        assert "user@example.com" not in result.text
        assert "[EMAIL_ADDRESS_1]" in result.text

    def test_cuit_detection(self, anon: Anonymizer) -> None:
        result = anon.anonymize("El CUIT es 20-12345678-6 de la empresa.")
        assert "20-12345678-6" not in result.text
        assert "[AR_CUIT_1]" in result.text

    def test_ip_detection(self, anon: Anonymizer) -> None:
        result = anon.anonymize("El servidor está en 10.0.0.1 y responde bien.")
        assert "10.0.0.1" not in result.text
        assert "[IP_ADDRESS_1]" in result.text

    def test_credit_card_detection(self, anon: Anonymizer) -> None:
        result = anon.anonymize("Pagó con 4532 0151 1283 0366 ayer.")
        assert "4532 0151 1283 0366" not in result.text
        assert "[CREDIT_CARD_1]" in result.text

    def test_api_key_detection(self, anon: Anonymizer) -> None:
        result = anon.anonymize("La key es sk-abcdefghijklmnopqrstuvwx y funciona.")
        assert "sk-abcdefghijklmnopqrstuvwx" not in result.text
        assert "[API_KEY_1]" in result.text


class TestTokenConsistency:
    def test_same_value_same_token(self, anon: Anonymizer) -> None:
        text = (
            "Enviar a user@test.com el reporte. "
            "Confirmar con user@test.com antes del lunes."
        )
        result = anon.anonymize(text)
        assert result.text.count("[EMAIL_ADDRESS_1]") == 2

    def test_different_values_different_tokens(self, anon: Anonymizer) -> None:
        text = "Contactar a a@test.com y b@test.com para coordinar."
        result = anon.anonymize(text)
        assert "[EMAIL_ADDRESS_1]" in result.text
        assert "[EMAIL_ADDRESS_2]" in result.text


class TestRoundTrip:
    def test_anonymize_restore_roundtrip(self, anon: Anonymizer) -> None:
        original = "El email de Juan es juan@empresa.com y su IP es 192.168.1.50."
        result = anon.anonymize(original)
        assert result.mapping is not None
        restored = Anonymizer.restore(result.text, result.mapping)
        assert "juan@empresa.com" in restored
        assert "192.168.1.50" in restored

    def test_irreversible_no_mapping(self, anon_irreversible: Anonymizer) -> None:
        result = anon_irreversible.anonymize("Email: admin@corp.com")
        assert result.mapping is None


class TestConfiguration:
    def test_entity_whitelist(self) -> None:
        anon = Anonymizer(entity_whitelist=["EMAIL_ADDRESS"])
        result = anon.anonymize("IP 10.0.0.1 email user@x.com")
        assert "[EMAIL_ADDRESS_1]" in result.text
        assert "10.0.0.1" in result.text

    def test_entity_blacklist(self) -> None:
        anon = Anonymizer(entity_blacklist=["IP_ADDRESS"])
        result = anon.anonymize("IP 10.0.0.1 email user@x.com")
        assert "10.0.0.1" in result.text
        assert "[EMAIL_ADDRESS_1]" in result.text

    def test_high_threshold_skips_low_confidence(self) -> None:
        anon_strict = Anonymizer(score_threshold=0.99)
        result = anon_strict.anonymize("El valor es 192.168.1.1 en la red.")
        assert "192.168.1.1" in result.text


class TestRestore:
    def test_restore_preserves_non_token_text(self) -> None:
        text = "Hola [PERSON_1], tu pedido está listo."
        mapping = {"[PERSON_1]": "Carlos"}
        restored = Anonymizer.restore(text, mapping)
        assert restored == "Hola Carlos, tu pedido está listo."

    def test_restore_multiple_tokens(self) -> None:
        text = "[PERSON_1] envió un email a [EMAIL_ADDRESS_1]."
        mapping = {"[PERSON_1]": "María", "[EMAIL_ADDRESS_1]": "maria@test.com"}
        restored = Anonymizer.restore(text, mapping)
        assert restored == "María envió un email a maria@test.com."
