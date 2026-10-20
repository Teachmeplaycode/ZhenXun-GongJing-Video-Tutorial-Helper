"""Build a source-only deployment bundle with an explicit allowlist."""
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parents[2]
output = Path("/private/tmp/gongjing-cloud-source.tar.gz")
trees = {"backend/modules": {".py"}, "backend/tests": {".py"},
         "front/src": {".js", ".jsx", ".css", ".svg"}, "front/public": {".svg", ".png", ".jpg", ".ico"},
         "deploy/huawei": {".py", ".sh", ".md"}}
files = [root / p for p in ("backend/app.py", "backend/cloud_app.py", "backend/pyproject.toml", "backend/uv.lock",
                           "front/package.json", "front/package-lock.json", "front/index.html", "front/vite.config.js")]
for directory, suffixes in trees.items():
    files.extend(p for p in (root / directory).rglob("*") if p.is_file() and p.suffix in suffixes
                 and "__pycache__" not in p.parts)
with tarfile.open(output, "w:gz") as archive:
    for path in sorted(set(files)):
        archive.add(path, arcname="gongjing/" + path.relative_to(root).as_posix(), recursive=False)
print(f"{output}: {len(set(files))} source files, {output.stat().st_size} bytes; no env, cookies, data, git or models")
