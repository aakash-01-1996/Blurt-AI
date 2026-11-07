import pytest
from blurt_core.config import Settings


def test_settings_defaults() -> None:
    s = Settings()
    assert s.storage_backend == "local"
    assert s.router_confidence_threshold == 0.7
    assert s.environment == "dev"


def test_default_secret_allowed_in_dev() -> None:
    s = Settings(environment="dev")
    assert s.jwt_secret == "dev-secret-change-in-production"


def test_empty_jwt_secret_rejected() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(jwt_secret="")


def test_default_secret_rejected_in_production() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(environment="production")


def test_real_secret_accepted_in_production() -> None:
    s = Settings(environment="production", jwt_secret="a-real-strong-secret")
    assert s.jwt_secret == "a-real-strong-secret"
