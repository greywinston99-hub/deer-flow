from pathlib import Path

from deerflow.config.app_config import AppConfig
from deerflow.config.model_config import ModelConfig


def _make_model(**overrides) -> ModelConfig:
    return ModelConfig(
        name="openai-responses",
        display_name="OpenAI Responses",
        description=None,
        use="langchain_openai:ChatOpenAI",
        model="gpt-5",
        **overrides,
    )


def test_responses_api_fields_are_declared_in_model_schema():
    assert "use_responses_api" in ModelConfig.model_fields
    assert "output_version" in ModelConfig.model_fields
    assert "supports_tool_calls" in ModelConfig.model_fields


def test_responses_api_fields_round_trip_in_model_dump():
    config = _make_model(
        api_key="$OPENAI_API_KEY",
        use_responses_api=True,
        output_version="responses/v1",
    )

    dumped = config.model_dump(exclude_none=True)

    assert dumped["use_responses_api"] is True
    assert dumped["output_version"] == "responses/v1"


def test_supports_tool_calls_defaults_to_true_for_backward_compatibility():
    config = _make_model()

    assert config.supports_tool_calls is True


def test_supports_tool_calls_can_be_disabled_explicitly():
    config = _make_model(supports_tool_calls=False)

    assert config.supports_tool_calls is False


def test_kimi_api_config_uses_direct_moonshot_endpoint():
    config_path = Path(__file__).resolve().parents[2] / "config.yaml"
    config = AppConfig.from_file(str(config_path))

    model = next(item for item in config.models if item.name == "kimi-k2.6-api")

    assert model.use == "deerflow.models.patched_deepseek:PatchedChatDeepSeek"
    assert model.model == "kimi-k2.6"
    assert model.api_base == "https://api.moonshot.cn/v1"
