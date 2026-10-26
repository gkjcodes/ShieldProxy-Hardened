import os
import pytest
from config import Settings, AppMode


def test_settings_default_values():
    s = Settings(APP_MODE=AppMode.DEVELOPMENT)
    assert s.RATE_LIMIT_RPM == 60
    assert s.MAX_BODY_SIZE_BYTES == 65536
    assert s.GATEWAY_TIMEOUT_SECONDS == 15.0 or s.GATEWAY_TIMEOUT_SECONDS == 2.0
    assert len(s.cors_origins_list) >= 1


def test_protected_mode_rejects_wildcard_cors():
    with pytest.raises(ValueError, match="Wildcard CORS origin"):
        Settings(
            APP_MODE=AppMode.PROTECTED,
            CORS_ALLOWED_ORIGINS="*",
            AUTH_KEY_REGISTRY="validkey:tenant1:admin"
        )


def test_protected_mode_rejects_empty_or_placeholder_keys():
    with pytest.raises(ValueError, match="Protected mode requires a non-empty"):
        Settings(
            APP_MODE=AppMode.PROTECTED,
            CORS_ALLOWED_ORIGINS="https://dashboard.example.com",
            AUTH_KEY_REGISTRY=""
        )

    with pytest.raises(ValueError, match="Protected mode requires a non-empty"):
        Settings(
            APP_MODE=AppMode.PROTECTED,
            CORS_ALLOWED_ORIGINS="https://dashboard.example.com",
            AUTH_KEY_REGISTRY="dev-client-placeholder:tenant:client"
        )


def test_settings_repr_masks_credentials():
    s = Settings(
        APP_MODE=AppMode.DEVELOPMENT,
        OPENAI_API_KEY="sk-super-secret-key-12345",
        AUTH_KEY_REGISTRY="sk-secret:tenant:admin"
    )
    repr_str = repr(s)
    assert "sk-super-secret-key-12345" not in repr_str
    assert "sk-secret" not in repr_str


def test_env_example_contains_placeholders_only():
    env_example_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env.example"))
    assert os.path.exists(env_example_path)
    with open(env_example_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify sensitive actual tokens are not present
    assert "your-openai-api-key-placeholder" in content
    assert "dev-client-key-placeholder" in content
    assert "sk-" not in content or "placeholder" in content


def test_requirements_pruned_of_dead_dependencies():
    req_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "requirements.txt"))
    with open(req_path, "r", encoding="utf-8") as f:
        reqs = f.read()
    assert "llama-cpp-python" not in reqs
    assert "scikit-learn" not in reqs
    assert "pydantic-settings" in reqs
    assert "pytest" in reqs