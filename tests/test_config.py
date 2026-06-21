from ares_insight.config import settings


def test_slice_defaults_sane():
    assert settings.nace_prefixes, "NACE vyrez nesmi byt prazdny"
    assert settings.region


def test_model_string_set():
    assert settings.anthropic_model
