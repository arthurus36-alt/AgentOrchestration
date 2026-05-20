import os
from src.common.config import Config



class TestConfig:
    def test_load_config(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text('{"app": {"name": "test", "port": 8080}}')
        config = Config(str(config_file))
        assert config.get("app.name") == "test"
        assert config.get("app.port") == 8080

    def test_default_value(self):
        config = Config()
        assert config.get("nonexistent.key", "default") == "default"

    def test_set_value(self):
        config = Config()
        config.set("database.host", "localhost")
        assert config.get("database.host") == "localhost"

    def test_env_override_booleans(self):
        os.environ["AO_FEATURE_ENABLED"] = "false"
        os.environ["AO_OTHER_FLAG"] = "  TrUe  "
        os.environ["AO_NORMAL_STRING"] = "falseish"
        os.environ["AO_ZERO"] = "0"

        config = Config()
        assert config.get("feature.enabled") is False
        assert config.get("other.flag") is True
        assert config.get("normal.string") == "falseish"
        assert config.get("zero") == "0"

        del os.environ["AO_FEATURE_ENABLED"]
        del os.environ["AO_OTHER_FLAG"]
        del os.environ["AO_NORMAL_STRING"]
        del os.environ["AO_ZERO"]
