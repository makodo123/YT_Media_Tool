"""將發行資料夾壓縮為 zip，並產生 sha256sum 格式的 .sha256 檔案。

用法：python scripts/make_release_zip.py dist/YT_Media_Tool dist/YT_Media_Tool-2.0.0-win64.zip
"""

from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path


def main(source: str, target: str) -> int:
    src, zip_path = Path(source), Path(target)
    if not src.is_dir():
        print(f"找不到發行資料夾：{src}", file=sys.stderr)
        return 1
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(src.rglob("*")):
            if path.is_file():
                # zip 內保留最上層資料夾名稱（解壓縮後為 YT_Media_Tool\\YT_Media_Tool.exe）
                zf.write(path, path.relative_to(src.parent).as_posix())
    digest = hashlib.sha256()
    with open(zip_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    sha_file = zip_path.with_name(zip_path.name + ".sha256")
    sha_file.write_text(f"{digest.hexdigest()}  {zip_path.name}\n", encoding="ascii")
    print(f"{zip_path}（{zip_path.stat().st_size / 1024 / 1024:.1f} MB）")
    print(f"SHA256：{digest.hexdigest()}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
