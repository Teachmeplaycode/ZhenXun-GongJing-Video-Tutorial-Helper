"""Exercise the actual bundle and ASR download scripts without external downloads."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_actual_bundle_includes_loadable_runtime_rules_but_no_private_files(tmp_path):
    output = tmp_path / "new-parent" / "source.tar.gz"
    subprocess.run([sys.executable, str(ROOT / "deploy/huawei/bundle.py"), "--output", str(output)], check=True)
    with tarfile.open(output) as archive:
        names = archive.getnames()
        assert "gongjing/backend/modules/antifraud/rules.json" in names
        assert not any("/backend/data/" in n or "/node_modules/" in n or "/.git/" in n
                       or Path(n).name in {".env", ".env.accounts", "wechat.txt"} for n in names)
        raw = archive.extractfile("gongjing/backend/modules/antifraud/rules.json").read()
    rules = tmp_path / "rules.json"
    rules.write_bytes(raw)
    from modules.antifraud.rules import RuleLibrary
    assert RuleLibrary.load(rules).rules


def test_bundle_default_respects_system_temp_directory(tmp_path):
    env = {"PATH": os.defpath, "TMPDIR": str(tmp_path)}
    subprocess.run([sys.executable, str(ROOT / "deploy/huawei/bundle.py")], env=env, check=True)
    assert (tmp_path / "gongjing-cloud-source.tar.gz").is_file()


@pytest.mark.parametrize("has_uv", [False, True])
def test_download_script_uses_available_installer_then_venv_python(tmp_path, has_uv):
    root = tmp_path / "project"
    script = root / "deploy/huawei/download-asr.sh"
    script.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "deploy/huawei/download-asr.sh", script)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "dirname").symlink_to(shutil.which("dirname"))
    venv_bin = root / "backend/.venv/bin"
    venv_bin.mkdir(parents=True)
    stub = "#!" + sys.executable + "\nimport json,os,sys\nwith open(os.environ['CALL_LOG'],'a') as f: f.write(json.dumps(sys.argv)+'\\n')\n"
    # All installer/model calls are recorded; the -c download payload is never evaluated.
    for target in [venv_bin / "python"] + ([bin_dir / "uv"] if has_uv else []):
        target.write_text(stub)
        target.chmod(0o755)
    log = tmp_path / "calls.jsonl"
    env = {"PATH": str(bin_dir), "CALL_LOG": str(log)}
    subprocess.run(["/bin/bash", str(script)], env=env, check=True)
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert len(calls) == 2
    assert calls[0][0] == (str(bin_dir / "uv") if has_uv else ".venv/bin/python")
    assert calls[0][1:3] == (["pip", "install"] if has_uv else ["-m", "pip"])
    assert calls[1][0] == ".venv/bin/python" and calls[1][1] == "-c"
    assert "snapshot_download" in calls[1][2]


@pytest.mark.parametrize("downloaded, explicit", [(True, None), (True, "custom-model"), (False, None), (False, "custom-model")])
def test_normal_start_prefers_downloaded_model_and_preserves_override(tmp_path, downloaded, explicit):
    root = tmp_path / "project"
    script = root / "deploy/huawei/start.sh"
    script.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "deploy/huawei/start.sh", script)
    local = tmp_path / "downloaded-model"
    if downloaded:
        local.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "dirname").symlink_to(shutil.which("dirname"))
    executable = root / "backend/.venv/bin/uvicorn"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!" + sys.executable + "\nimport json,os\nwith open(os.environ['CALL_LOG'],'w') as f: json.dump({'ASR_MODEL':os.environ['ASR_MODEL']},f)\n")
    executable.chmod(0o755)
    log = tmp_path / "started.json"
    env = {"PATH": str(bin_dir), "CALL_LOG": str(log), "ASR_LOCAL_MODEL_DIR": str(local)}
    if explicit is not None:
        env["ASR_MODEL"] = explicit
    subprocess.run(["/bin/bash", str(script)], env=env, check=True)
    assert json.loads(log.read_text())["ASR_MODEL"] == (explicit or (str(local) if downloaded else "small"))
