"""Build a source-only deployment bundle with an explicit allowlist."""
import argparse
from pathlib import Path
import tarfile
import tempfile


def build_bundle(root: Path, output: Path) -> int:
    trees = {"backend/modules": {".py"}, "backend/tests": {".py"},
             "front/src": {".js", ".jsx", ".css", ".svg"}, "front/public": {".svg", ".png", ".jpg", ".ico"},
             "deploy/huawei": {".py", ".sh", ".md"}}
    files = [root / p for p in ("backend/app.py", "backend/cloud_app.py", "backend/pyproject.toml", "backend/uv.lock",
                               "backend/modules/antifraud/rules.json",
                               "front/package.json", "front/package-lock.json", "front/index.html", "front/vite.config.js")]
    for directory, suffixes in trees.items():
        files.extend(p for p in (root / directory).rglob("*") if p.is_file() and not p.is_symlink()
                     and p.suffix in suffixes and "__pycache__" not in p.parts)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "w:gz") as archive:
        for path in sorted(set(files)):
            archive.add(path, arcname="gongjing/" + path.relative_to(root).as_posix(), recursive=False)
    return len(set(files))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(tempfile.gettempdir()) / "gongjing-cloud-source.tar.gz")
    args = parser.parse_args()
    count = build_bundle(Path(__file__).resolve().parents[2], args.output)
    print(f"{args.output}: {count} source files, {args.output.stat().st_size} bytes; no env, cookies, data, git or models")


if __name__ == "__main__":
    main()
