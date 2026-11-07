"""Tests for administrative keyword generation logic."""

import pytest
from app.services.discovery import generate_orthogonal_keywords


def test_generate_keywords_administrative_only():
    current_address = {
        "ward": "Phường Hòa Khánh Nam",
        "district": "Quận Liên Chiểu",
        "city": "Thành phố Đà Nẵng",
    }
    keywords = generate_orthogonal_keywords(current_address, max_keywords=3)

    assert len(keywords) == 3
    # Check that keywords use administrative units
    assert any("Hòa Khánh Nam" in kw for kw in keywords)


def test_generate_keywords_fallback():
    current_address = {}
    keywords = generate_orthogonal_keywords(current_address, max_keywords=3)
    assert len(keywords) > 0
    assert any("Đà Nẵng" in kw for kw in keywords)
