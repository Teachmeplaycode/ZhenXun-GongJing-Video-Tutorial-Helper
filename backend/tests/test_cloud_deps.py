"""The cloud install must never pull the libGL opencv: declaration-level guarantees.

rapidocr-onnxruntime declares `opencv-python` (needs libGL on headless Linux, and collides with
the project's opencv-python-headless — both ship cv2). The fix is declarative: the uv exclusion in
pyproject.toml keeps it out of the resolution, and deploy/huawei/prepare.sh installs rapidocr with
--no-deps plus its real requirements explicitly. These tests pin all of that, offline.
"""
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text())
PREPARE = (ROOT.parent / "deploy" / "huawei" / "prepare.sh").read_text()


def test_the_only_cv2_is_the_headless_build():
    deps = PYPROJECT["project"]["dependencies"]
    names = {d.split(";")[0].strip().split("[")[0].split(">")[0].split("<")[0].split("=")[0].split("!")[0].strip().lower() for d in deps}
    assert "opencv-python-headless" in names, "the project must keep depending on the headless cv2"
    assert "opencv-python" not in names, "the libGL opencv must never be a direct dependency"


def test_the_cloud_extra_does_not_directly_ask_for_opencv_python():
    cloud = PYPROJECT["project"]["optional-dependencies"]["cloud"]
    names = {c.split(";")[0].strip().split("[")[0].split(">")[0].split("<")[0].split("=")[0].strip().lower() for c in cloud}
    assert "opencv-python" not in names
    assert any("rapidocr" in n for n in names), "the cloud extra should still bring rapidocr"


def test_the_uv_exclusion_keeps_rapidocrs_opencv_out_of_the_resolution():
    assert "opencv-python" in PYPROJECT["tool"]["uv"]["exclude-dependencies"]



def test_prepare_sh_installs_headless_first_and_rapidocr_without_its_dependencies():
    assert PREPARE.index("opencv-python-headless") < PREPARE.index("--no-deps 'rapidocr-onnxruntime>=1.4,<2'"), \
        "the headless cv2 must be installed before rapidocr, so cv2 is never the libGL build"
    after = PREPARE[PREPARE.index("--no-deps 'rapidocr-onnxruntime>=1.4,<2'"):]
    for need in ("onnxruntime", "pyclipper", "PyYAML", "Shapely"):
        assert need in after, f"rapidocr's real dependency {need} must be installed explicitly"
