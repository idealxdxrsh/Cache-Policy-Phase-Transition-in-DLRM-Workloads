"""Extract every archive in SRC into DST, recursively unpacking nested archives.

Usage: python -I safe_extract.py SRC DST
"""
import gzip
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path


def extract(path: Path, dst: Path) -> None:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            z.extractall(dst)
    elif tarfile.is_tarfile(path):
        with tarfile.open(path) as t:
            t.extractall(dst, filter="data")
    elif path.suffix == ".gz":
        with gzip.open(path, "rb") as fi, open(dst / path.stem, "wb") as fo:
            shutil.copyfileobj(fi, fo, 1 << 24)
    else:
        return
    print(f"extracted {path.name}")
    if path.is_relative_to(dst):
        path.unlink()


def main() -> None:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    dst.mkdir(parents=True, exist_ok=True)
    for p in sorted(src.iterdir()):
        extract(p, dst)
    # Nested archives (e.g. a .tar.gz inside a .zip)
    for _ in range(3):
        nested = [p for p in dst.rglob("*") if p.is_file()
                  and p.suffix in (".zip", ".gz", ".tar", ".tgz")]
        if not nested:
            break
        for p in nested:
            extract(p, p.parent)


if __name__ == "__main__":
    main()
