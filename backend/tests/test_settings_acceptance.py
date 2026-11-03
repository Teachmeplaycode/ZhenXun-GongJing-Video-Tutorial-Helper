"""Behavioral regressions found during independent acceptance of the local settings API."""
import os
import stat

import pytest
from fastapi.testclient import TestClient

from modules import settings as config
from modules.llm import LLMConfig
from test_settings_api import files  # isolated config files, never real credentials


def client(*, peer="127.0.0.1", host="127.0.0.1"):
    import app
    return TestClient(app.app, base_url=f"http://{host}", client=(peer, 45123))


@pytest.mark.parametrize("name,value", [
    ("LLM_API_KEY", "test-key\nLLM_MODEL=injected"),
    ("LLM_MODEL", "bad\x00model"),
    ("OLLAMA_NUM_CTX", "65536.5"),
    ("OLLAMA_NUM_CTX", "-1"),
    ("LLM_TEMPERATURE", "NaN"),
    ("LLM_TEMPERATURE", "3"),
    ("LLM_FIRST_TOKEN_TIMEOUT", "0"),
    ("LLM_BASE_URL", "file:///tmp/model"),
    ("LLM_BASE_URL", "http://user:password@example.com/v1"),
    ("LLM_BASE_URL", "https://example.com/v1?api_key=private"),
])
def test_invalid_values_never_modify_configuration(files, name, value):
    config.write_local({"LLM_MODEL": "original"})
    before = files[2].read_bytes()
    response = client().put("/api/settings", json={"values": {name: value}})
    assert response.status_code == 400
    assert files[2].read_bytes() == before


def test_remote_peer_cannot_read_or_write_local_settings(files):
    c = client(peer="192.0.2.10")
    assert c.get("/api/settings").status_code == 403
    assert c.put("/api/settings", json={"values": {"LLM_MODEL": "remote"}}).status_code == 403
    assert not files[2].exists()


def test_rebound_host_is_refused_even_from_loopback(files):
    assert client(host="attacker.example").get("/api/settings").status_code == 403


def test_public_mode_does_not_expose_server_configuration(files, monkeypatch):
    config.write_local({"LLM_BASE_URL": "https://private-model.example/v1"})
    monkeypatch.setenv("PUBLIC_DEMO", "1")
    response = client().get("/api/settings")
    assert response.status_code == 200
    assert response.json()["readonly"] is True
    assert response.json()["values"] == {}
    assert "private-model.example" not in response.text


def test_alias_credential_reports_its_actual_source(files):
    files[0].write_text("DEEPSEEK_API_KEY=test-inherited-key\n", encoding="utf-8")
    value = client().get("/api/settings").json()["values"]["LLM_API_KEY"]
    assert value["configured"] is True
    assert value["source"] == "env"


def test_empty_environment_value_still_has_precedence(files, monkeypatch):
    config.write_local({"LLM_MODEL": "local-model"})
    monkeypatch.setenv("LLM_MODEL", "")
    value = client().get("/api/settings").json()["values"]["LLM_MODEL"]
    assert value["value"] == ""
    assert value["source"] == "environment"
    assert value["overridden_by_env"] is True


def test_clear_optional_override_restores_model_defaults(files):
    config.write_local({"LLM_API_KEY": "test-only-key", "LLM_MODEL": "custom"})
    response = client().put("/api/settings", json={"values": {"LLM_MODEL": ""}})
    assert response.status_code == 200
    assert LLMConfig.from_env().model == "deepseek-flash"


def test_key_only_setup_keeps_valid_defaults_and_never_echoes_key(files):
    response = client().put("/api/settings", json={"values": {"LLM_API_KEY": "test-first-run"}})
    assert response.status_code == 200
    assert "test-first-run" not in response.text
    model = LLMConfig.from_env()
    assert model.base_url == "https://api.deepseek.com"
    assert model.model == "deepseek-flash"


def test_malformed_payload_does_not_echo_secret_input(files):
    response = client().put("/api/settings", json={"values": {"LLM_API_KEY": ["test-do-not-echo"]}})
    assert response.status_code == 422
    assert "test-do-not-echo" not in response.text


def test_existing_credential_url_is_not_reflected(files):
    files[0].write_text("CN_PROXY=http://user:test-proxy-password@example.com:8080\n", encoding="utf-8")
    response = client().get("/api/settings")
    assert "test-proxy-password" not in response.text


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits do not describe Windows ACLs")
def test_temporary_config_is_private_before_replacement(files, monkeypatch):
    real_replace = config.os.replace
    modes = []
    def replace(source, destination):
        modes.append(stat.S_IMODE(os.stat(source).st_mode))
        return real_replace(source, destination)
    monkeypatch.setattr(config.os, "replace", replace)
    config.write_local({"LLM_API_KEY": "test-private"})
    assert modes == [0o600]


def test_failed_replace_keeps_old_file_and_cleans_temporary_file(files, monkeypatch):
    config.write_local({"LLM_MODEL": "original"})
    before = files[2].read_bytes()
    def unavailable(*args):
        raise PermissionError("simulated read-only destination")
    monkeypatch.setattr(config.os, "replace", unavailable)
    with pytest.raises(OSError):
        config.write_local({"LLM_MODEL": "new"})
    assert files[2].read_bytes() == before
    assert list(files[2].parent.glob(".env.local.*")) == []
