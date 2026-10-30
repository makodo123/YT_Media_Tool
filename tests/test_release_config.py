"""發行設定的一致性檢查：版本號、安裝程式設定與程式碼中的名稱必須一致。"""

import re
import tomllib
from pathlib import Path

import pytest

from yt_media_tool import APP_ID, __version__
from yt_media_tool.utils.win_job import APP_MUTEX_NAME

ROOT = Path(__file__).resolve().parents[1]
ISS = (ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8-sig")


def test_version_is_consistent_everywhere():
    bat = (ROOT / "scripts" / "build_exe.bat").read_text(encoding="utf-8")
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert re.search(r'set "VERSION=([^"]+)"', bat).group(1) == __version__
    assert pyproject["project"]["version"] == __version__


def test_installer_names_match_code():
    assert re.search(r"^AppMutex=(.+)$", ISS, re.M).group(1).strip() == APP_MUTEX_NAME
    assert re.search(r'#define AppDataFolder "([^"]+)"', ISS).group(1) == APP_ID
    assert re.search(r'#define AppExeName "([^"]+)"', ISS).group(1) == "YT_Media_Tool.exe"
    assert "OutputBaseFilename=YT_Media_Tool-{#AppVersion}-win64-setup" in ISS


def test_installer_files_are_utf8_with_bom():
    for name in ("installer.iss", "installer_notice.txt", "ChineseTraditional.isl"):
        data = (ROOT / "packaging" / name).read_bytes()
        assert data.startswith(b"\xef\xbb\xbf"), name
        assert b"\r\n" in data, name


def render_version_info() -> str:
    template = (ROOT / "packaging" / "version_info.txt").read_text(encoding="utf-8")
    numbers = [int(p) for p in re.findall(r"\d+", __version__)[:3]]
    return template.replace("$VERSION_TUPLE$", repr(tuple(numbers + [0] * (4 - len(numbers))))) \
                   .replace("$VERSION$", __version__)


def test_version_info_template_has_no_hardcoded_version():
    rendered = render_version_info()
    assert "$" not in rendered.split("\n", 2)[2]
    assert f"'{__version__}'" in rendered


def test_version_info_template_renders_valid_resource(tmp_path):
    pytest.importorskip("pefile")  # PyInstaller 只在 Windows 安裝 pefile
    from PyInstaller.utils.win32 import versioninfo

    path = tmp_path / "version_info.txt"
    path.write_text(render_version_info(), encoding="utf-8")
    assert __version__ in str(versioninfo.load_version_info_from_text_file(str(path)))


def test_build_installer_command(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_installer", ROOT / "scripts" / "build_installer.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.read_version() == __version__
    cmd = module.iscc_command(Path("C:/Inno/ISCC.exe"), "9.9.9")
    assert cmd[1] == "/DAppVersion=9.9.9" and cmd[-1].endswith("installer.iss")
    setup = tmp_path / "x-setup.exe"
    setup.write_bytes(b"abc")
    digest = module.write_sha256(setup)
    assert (tmp_path / "x-setup.exe.sha256").read_text(encoding="ascii") == f"{digest}  x-setup.exe\n"
