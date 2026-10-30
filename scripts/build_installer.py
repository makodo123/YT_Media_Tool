"""以 Inno Setup 建立 Windows 安裝程式（需先執行 build_exe.bat 產生 dist\\YT_Media_Tool）。

用法：python scripts/build_installer.py
產出：dist/YT_Media_Tool-<版本>-win64-setup.exe 與同名 .sha256

ISCC 尋找順序：環境變數 ISCC → PATH → Inno Setup 6 的預設安裝位置。
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
SOURCE = DIST / "YT_Media_Tool"
SCRIPT = ROOT / "packaging" / "installer.iss"


def read_version() -> str:
    text = (ROOT / "src" / "yt_media_tool" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not match:
        raise SystemExit("無法從 __init__.py 讀取版本號")
    return match.group(1)


def find_iscc() -> Path | None:
    candidates = [os.environ.get("ISCC"), shutil.which("iscc"), shutil.which("ISCC")]
    for base in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        root = os.environ.get(base)
        if root:
            sub = "Programs\\Inno Setup 6" if base == "LOCALAPPDATA" else "Inno Setup 6"
            candidates.append(str(Path(root) / sub / "ISCC.exe"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


def iscc_command(iscc: Path, version: str) -> list[str]:
    return [str(iscc), f"/DAppVersion={version}", f"/DSourceDir={SOURCE}", f"/DOutputDir={DIST}", str(SCRIPT)]


def write_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    path.with_name(path.name + ".sha256").write_text(f"{digest.hexdigest()}  {path.name}\n", encoding="ascii")
    return digest.hexdigest()


def main() -> int:
    if not (SOURCE / "YT_Media_Tool.exe").is_file():
        print(f"找不到 {SOURCE / 'YT_Media_Tool.exe'}，請先執行 scripts\\build_exe.bat", file=sys.stderr)
        return 1
    iscc = find_iscc()
    if iscc is None:
        print("找不到 Inno Setup 6 的 ISCC.exe。請安裝：winget install -e --id JRSoftware.InnoSetup", file=sys.stderr)
        return 1
    version = read_version()
    print(f"使用 {iscc} 建置 {version} 安裝程式")
    result = subprocess.run(iscc_command(iscc, version), check=False)
    if result.returncode != 0:
        return result.returncode
    setup = DIST / f"YT_Media_Tool-{version}-win64-setup.exe"
    if not setup.is_file():
        print(f"ISCC 執行完畢但找不到 {setup}", file=sys.stderr)
        return 1
    print(f"{setup}（{setup.stat().st_size / 1024 / 1024:.1f} MB）")
    print(f"SHA256：{write_sha256(setup)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
