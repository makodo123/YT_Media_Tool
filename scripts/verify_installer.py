"""在 Windows 上實際以靜默模式安裝、啟動、解除安裝，驗證安裝程式（供 CI 使用）。

用法：python scripts/verify_installer.py [dist\\YT_Media_Tool-<版本>-win64-setup.exe]

檢查：安裝檔可執行、檔案與捷徑建立、「應用程式」清單登錄、已安裝的 EXE 可啟動、
隨附 FFmpeg 可實際轉檔，以及解除安裝後檔案、捷徑與登錄都被移除。
會在目前使用者的開始功能表 / 桌面短暫建立捷徑，結束時由解除安裝移除。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_dist import ffmpeg_functional_checks  # noqa: E402

APP_ID = "{8C2F6B1E-5D3A-4E7B-9A1C-2F4D6E8B0A13}_is1"
SHORTCUT = "YT Media Tool.lnk"


def uninstall_key_exists() -> tuple[bool, str]:
    import winreg

    path = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            return True, str(winreg.QueryValueEx(key, "DisplayVersion")[0])
    except OSError:
        return False, ""


def shortcuts() -> list[Path]:
    appdata = Path(os.environ["APPDATA"])
    start_menu = appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / SHORTCUT
    desktop = Path(os.environ["USERPROFILE"]) / "Desktop" / SHORTCUT
    return [start_menu, desktop]


def main(argv: list[str]) -> int:
    if not sys.platform.startswith("win"):
        print("此檢查只能在 Windows 上執行", file=sys.stderr)
        return 1
    setup = Path(argv[0]) if argv else next(iter(sorted((ROOT / "dist").glob("YT_Media_Tool-*-win64-setup.exe"))), None)
    if setup is None or not setup.is_file():
        print("找不到安裝檔，請先執行 scripts/build_installer.py", file=sys.stderr)
        return 1

    work = Path(tempfile.mkdtemp(prefix="ytmt_installer_"))
    install_dir, data_dir = work / "app", work / "data"
    checks: list[tuple[str, bool]] = []
    try:
        result = subprocess.run([str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER",
                                 f"/DIR={install_dir}", f"/LOG={work / 'install.log'}", "/TASKS=desktopicon"],
                                timeout=600, check=False)
        exe = install_dir / "YT_Media_Tool.exe"
        checks.append(("靜默安裝成功", result.returncode == 0 and exe.is_file()))
        checks.append(("安裝 _internal 與隨附元件",
                       (install_dir / "_internal" / "ffmpeg" / "ffmpeg.exe").is_file()
                       and (install_dir / "_internal" / "deno" / "deno.exe").is_file()))
        checks.append(("解除安裝程式存在", (install_dir / "unins000.exe").is_file()))
        start_menu, desktop = shortcuts()
        checks.append(("開始功能表捷徑", start_menu.is_file()))
        checks.append(("桌面捷徑", desktop.is_file()))
        registered, version = uninstall_key_exists()
        checks.append((f"已登錄於「應用程式」清單（版本 {version}）", registered))

        env = dict(os.environ, YTMT_DATA_DIR=str(data_dir), QT_QPA_PLATFORM="offscreen")
        smoke = subprocess.run([str(exe), "--smoke-test"], env=env, timeout=120, check=False)
        checks.append(("已安裝的程式可啟動（--smoke-test）", smoke.returncode == 0))
        checks.append(("資料寫入使用者資料夾而非安裝資料夾",
                       (data_dir / "yt_media_tool.sqlite3").is_file() and not any(install_dir.rglob("*.sqlite3"))))
        checks += [(f"安裝後 {name}", ok) for name, ok in
                   ffmpeg_functional_checks(install_dir / "_internal" / "ffmpeg", ".exe")]

        # 解除安裝程式會複製自己到暫存資料夾後重新執行，原程序立即結束，因此輪詢等待完成
        subprocess.run([str(install_dir / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                       timeout=120, check=False)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline and (exe.exists() or uninstall_key_exists()[0]):
            time.sleep(1)
        checks.append(("解除安裝後程式檔已移除", not exe.exists() and not (install_dir / "_internal").exists()))
        checks.append(("解除安裝後捷徑已移除", not start_menu.exists() and not desktop.exists()))
        checks.append(("解除安裝後已從「應用程式」清單移除", not uninstall_key_exists()[0]))
        checks.append(("解除安裝不刪除使用者資料（靜默模式預設保留）", (data_dir / "yt_media_tool.sqlite3").is_file()))
    except (OSError, subprocess.SubprocessError) as exc:
        checks.append((f"安裝程式檢查中斷（{exc}）", False))
    finally:
        shutil.rmtree(work, ignore_errors=True)

    ok = True
    for name, passed in checks:
        print(f"[{'OK' if passed else 'FAIL'}] {name}")
        ok &= passed
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
