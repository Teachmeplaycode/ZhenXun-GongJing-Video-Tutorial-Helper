"""Tests for the cross-platform launcher and cv_compat Unicode-path wrapper.

The launcher tests run on any platform: they invoke ``start.py --check`` as a
subprocess and check its exit code and output.  The cv_compat tests verify that
the wrapper produces the same result as cv2 on the current platform (on Linux
and macOS the wrapper is a direct passthrough; on Windows it uses np.fromfile
+ cv2.imdecode to handle non-ASCII paths).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent

# ── cv_compat ────────────────────────────────────────────────────────────


def test_imread_returns_same_as_cv2(tmp_path):
    from modules.cv_compat import imread

    img = np.full((30, 40, 3), 128, dtype=np.uint8)
    path = tmp_path / "frame.jpg"
    cv2.imwrite(str(path), img)
    result = imread(path)
    assert result is not None
    assert result.shape == (30, 40, 3)


def test_imwrite_round_trips(tmp_path):
    from modules.cv_compat import imwrite, imread

    img = np.full((20, 20, 3), 200, dtype=np.uint8)
    path = tmp_path / "out.jpg"
    assert imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    back = imread(path)
    assert back is not None
    assert back.shape == (20, 20, 3)


def test_imread_missing_file_returns_none(tmp_path):
    from modules.cv_compat import imread

    assert imread(tmp_path / "does_not_exist.jpg") is None


def test_imread_gray(tmp_path):
    from modules.cv_compat import imread_gray

    img = np.full((10, 10, 3), 50, dtype=np.uint8)
    path = tmp_path / "gray.png"
    cv2.imwrite(str(path), img)
    result = imread_gray(path)
    assert result is not None
    assert result.ndim == 2


def test_imwrite_with_unicode_path(tmp_path):
    """A path with non-ASCII characters should round-trip through imwrite/imread."""
    from modules.cv_compat import imwrite, imread

    folder = tmp_path / "视频文件夹"
    folder.mkdir()
    path = folder / "帧_001.jpg"
    img = np.zeros((15, 15, 3), dtype=np.uint8)
    img[5:10, 5:10] = 255
    assert imwrite(path, img)
    back = imread(path)
    assert back is not None
    assert back.shape == (15, 15, 3)


# ── start.py launcher ────────────────────────────────────────────────────


def _run_launcher(*args: str, timeout: float = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "start.py"), *args],
        capture_output=True, text=True, encoding="utf-8", timeout=timeout,
    )


def test_check_mode_exits_zero_or_one():
    """--check should exit 0 (tools present) or 1 (tools missing), never crash."""
    r = _run_launcher("--check", timeout=15)
    assert r.returncode in (0, 1), f"unexpected exit {r.returncode}\n{r.stdout}\n{r.stderr}"
    assert "GongJ!ng?" in r.stdout


def test_check_mode_reports_python():
    r = _run_launcher("--check", timeout=15)
    assert "Python" in r.stdout


def test_check_mode_reports_ports():
    r = _run_launcher("--check", timeout=15)
    assert "端口" in r.stdout
    assert "8000" in r.stdout
    assert "5173" in r.stdout


def test_invalid_arg_exits_nonzero():
    r = _run_launcher("--no-such-flag", timeout=10)
    assert r.returncode != 0


def test_help_exits_zero():
    r = _run_launcher("--help", timeout=10)
    assert r.returncode == 0
    assert "--check" in r.stdout
    assert "--no-browser" in r.stdout
    assert "--skip-install" in r.stdout


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX SO_REUSEADDR / TIME_WAIT behavior')
def test_recently_stopped_service_does_not_block_restart(monkeypatch):
    import importlib.util
    import socket
    monkeypatch.syspath_prepend(str(ROOT))
    spec = importlib.util.spec_from_file_location('launcher_acceptance', ROOT / 'start.py')
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    with socket.socket() as listener, socket.socket() as client:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        listener.listen()
        client.connect(('127.0.0.1', port))
        peer, _ = listener.accept()
        peer.close()
        assert client.recv(1) == b''
    assert launcher.port_in_use(port) is False
