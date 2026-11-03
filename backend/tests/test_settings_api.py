"""Settings panel API: desensitising secrets, keep/clear, env override, validation, local-only,
public-demo lock, and rebuilding the LLM client on a model change."""
import pytest
from fastapi.testclient import TestClient

from modules import settings as settings_module


@pytest.fixture
def files(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    accounts_file = tmp_path / ".env.accounts"
    local = tmp_path / ".env.local"
    monkeypatch.setattr(settings_module, "ENV_FILE", env)
    monkeypatch.setattr(settings_module, "ACCOUNTS_FILE", accounts_file)
    monkeypatch.setattr(settings_module, "LOCAL_FILE", local)
    from modules import accounts
    monkeypatch.setattr(accounts, "ENV_FILE", env)
    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", accounts_file)
    for key in ("LLM_API_KEY", "DEEPSEEK_API_KEY", "TAVILY_API_KEY", "LLM_PROVIDER", "LLM_MODEL",
                "OLLAMA_NUM_CTX", "KEEP_UPLOADS", "PUBLIC_DEMO"):
        monkeypatch.delenv(key, raising=False)
    return env, accounts_file, local


def _client():
    import app
    return TestClient(app.app, base_url="http://127.0.0.1", client=("127.0.0.1", 45123))


def test_get_desensitises_secrets(files):
    settings_module.write_local({"LLM_API_KEY": "sk-secret-123"})
    client = _client()
    text = client.get("/api/settings", headers={"Origin": "http://localhost:5173"}).text
    assert "sk-secret-123" not in text
    body = client.get("/api/settings", headers={"Origin": "http://localhost:5173"}).json()
    assert body["values"]["LLM_API_KEY"]["configured"] is True
    assert "value" not in body["values"]["LLM_API_KEY"]


def test_put_writes_local_and_applies(files):
    client = _client()
    r = client.put("/api/settings", headers={"Origin": "http://localhost:5173"},
                   json={"values": {"LLM_MODEL": "deepseek-chat"}, "clear": []})
    assert r.status_code == 200
    _, _, local = files
    assert "LLM_MODEL=deepseek-chat" in local.read_text(encoding="utf-8")
    assert settings_module.settings()["LLM_MODEL"] == "deepseek-chat"


def test_write_local_is_utf8(files):
    settings_module.write_local({"CN_PROXY": "http://中文代理:8080"})
    _, _, local = files
    assert "中文代理" in local.read_text(encoding="utf-8")
    assert settings_module.read_local()["CN_PROXY"] == "http://中文代理:8080"


def test_secret_empty_keeps_old(files):
    settings_module.write_local({"LLM_API_KEY": "sk-old"})
    client = _client()
    r = client.put("/api/settings", headers={"Origin": "http://localhost:5173"},
                   json={"values": {"LLM_API_KEY": ""}, "clear": []})
    assert r.status_code == 200
    assert r.json()["values"]["LLM_API_KEY"]["configured"] is True
    assert settings_module.read_local()["LLM_API_KEY"] == "sk-old"


def test_secret_clear_removes(files):
    settings_module.write_local({"LLM_API_KEY": "sk-old"})
    client = _client()
    r = client.put("/api/settings", headers={"Origin": "http://localhost:5173"},
                   json={"values": {}, "clear": ["LLM_API_KEY"]})
    assert r.status_code == 200
    assert r.json()["values"]["LLM_API_KEY"]["configured"] is False
    assert "LLM_API_KEY" not in settings_module.read_local()


def test_env_override_reported(files, monkeypatch):
    settings_module.write_local({"LLM_MODEL": "from-file"})
    monkeypatch.setenv("LLM_MODEL", "from-env")
    client = _client()
    v = client.get("/api/settings", headers={"Origin": "http://localhost:5173"}).json()["values"]["LLM_MODEL"]
    assert v["value"] == "from-env" and v["overridden_by_env"] is True and v["source"] == "environment"


def test_source_local_reported(files):
    settings_module.write_local({"LLM_MODEL": "from-panel"})
    client = _client()
    v = client.get("/api/settings", headers={"Origin": "http://localhost:5173"}).json()["values"]["LLM_MODEL"]
    assert v["value"] == "from-panel" and v["source"] == "local" and v["overridden_by_env"] is False


def test_unknown_field_rejected(files):
    client = _client()
    r = client.put("/api/settings", headers={"Origin": "http://localhost:5173"},
                   json={"values": {"NOPE": "x"}, "clear": []})
    assert r.status_code == 400


def test_number_validation(files):
    client = _client()
    r = client.put("/api/settings", headers={"Origin": "http://localhost:5173"},
                   json={"values": {"OLLAMA_NUM_CTX": "not-a-number"}, "clear": []})
    assert r.status_code == 400


def test_select_validation(files):
    client = _client()
    r = client.put("/api/settings", headers={"Origin": "http://localhost:5173"},
                   json={"values": {"LLM_PROVIDER": "bogus"}, "clear": []})
    assert r.status_code == 400


def test_cross_site_refused(files):
    client = _client()
    r = client.put("/api/settings", headers={"Origin": "https://evil.example"},
                   json={"values": {}, "clear": []})
    assert r.status_code == 403


def test_public_demo_rejects_write(files, monkeypatch):
    monkeypatch.setenv("PUBLIC_DEMO", "1")
    client = _client()
    r = client.put("/api/settings", json={"values": {"LLM_MODEL": "x"}, "clear": []})
    assert r.status_code in (401, 403)


def test_reset_llm_on_provider_change(files, monkeypatch):
    import app
    sentinel = object()
    monkeypatch.setattr(app, "llm", sentinel)
    monkeypatch.setattr(app, "_stale_llm", [])
    client = _client()
    r = client.put("/api/settings", headers={"Origin": "http://localhost:5173"},
                   json={"values": {"LLM_PROVIDER": "ollama"}, "clear": []})
    assert r.status_code == 200
    assert app.llm is None
    assert sentinel in app._stale_llm


def test_non_llm_change_keeps_client(files, monkeypatch):
    import app
    sentinel = object()
    monkeypatch.setattr(app, "llm", sentinel)
    monkeypatch.setattr(app, "_stale_llm", [])
    client = _client()
    r = client.put("/api/settings", headers={"Origin": "http://localhost:5173"},
                   json={"values": {"BROWSER": "off"}, "clear": []})
    assert r.status_code == 200
    assert app.llm is sentinel
