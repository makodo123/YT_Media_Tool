"""偵測 Claude Desktop 與 Codex 的設定檔，並在使用者按下按鈕時加入 YT Media Tool 的 MCP 設定。

修改的是其他程式的設定檔，因此：
- 只在使用者按下按鈕時寫入，不在背景自動修改。
- 只新增或更新 `yt-media-tool` 這一項，其他內容原樣保留；寫入前先備份原檔。
- 原檔格式錯誤（例如手動改壞）時不修改，回報原因。
- 先寫暫存檔再取代，寫到一半中斷也不會留下損壞的設定檔。

Claude Code 的設定檔（~/.claude.json）含大量其他資料且執行中會頻繁寫入，不自動修改，只提供指令讓使用者執行。
"""

from __future__ import annotations

import json
import os
import re
import tomllib
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

SERVER_KEY = "yt-media-tool"


class ConfigState(str, Enum):
    NOT_FOUND = "not_found"  # 沒有偵測到這個 AI 助理
    NOT_CONFIGURED = "not_configured"  # 有安裝，尚未加入
    CONFIGURED = "configured"  # 已加入且路徑正確
    OUTDATED = "outdated"  # 已加入但程式路徑不同（例如改裝到別的資料夾）
    INVALID = "invalid"  # 設定檔格式錯誤，不會修改


@dataclass(frozen=True)
class ClientConfig:
    name: str  # 顯示名稱，例如「Claude Desktop」
    path: Path | None  # 設定檔位置；None 表示沒有偵測到
    state: ConfigState
    detail: str = ""  # INVALID 時的原因


class ConfigError(Exception):
    """無法修改設定檔；訊息直接顯示給使用者。"""


# ---------------------------------------------------------------------------
# 偵測
# ---------------------------------------------------------------------------
def claude_desktop_config_path() -> Path | None:
    """Claude Desktop 的設定檔位置（一般安裝版或 Microsoft Store 版）；沒有安裝時回傳 None。"""
    candidates = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "Claude")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        # Microsoft Store 版（MSIX）的設定寫在套件的虛擬化資料夾
        candidates += sorted((Path(local) / "Packages").glob("Claude_*/LocalCache/Roaming/Claude"))
    for folder in candidates:
        if folder.is_dir():
            return folder / "claude_desktop_config.json"
    return None


def codex_config_path() -> Path | None:
    """Codex 的設定檔位置（CODEX_HOME 或 ~/.codex）；沒有安裝時回傳 None。"""
    home = os.environ.get("CODEX_HOME")
    folder = Path(home) if home else Path.home() / ".codex"
    return folder / "config.toml" if folder.is_dir() else None


def claude_code_command(command: list[str]) -> str:
    """Claude Code 的加入指令（在命令提示字元執行一次）。"""
    return f"claude mcp add --scope user {SERVER_KEY} -- " + " ".join(_quote(part) for part in command)


def _quote(part: str) -> str:
    return f'"{part}"' if " " in part or not part else part


# ---------------------------------------------------------------------------
# Claude Desktop（JSON）
# ---------------------------------------------------------------------------
def _read_claude_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"無法讀取設定檔：{exc}") from exc
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ConfigError(f"設定檔不是正確的 JSON 格式（第 {getattr(exc, 'lineno', '?')} 行附近）") from exc
    if not isinstance(data, dict):
        raise ConfigError("設定檔的內容不是 JSON 物件（{ … }）")
    servers = data.get("mcpServers")
    if servers is not None and not isinstance(servers, dict):
        raise ConfigError("設定檔中的 mcpServers 不是 JSON 物件")
    return data


def claude_desktop_status(command: list[str], path: Path | None = None) -> ClientConfig:
    path = path or claude_desktop_config_path()
    if path is None:
        return ClientConfig("Claude Desktop", None, ConfigState.NOT_FOUND)
    try:
        data = _read_claude_json(path)
    except ConfigError as exc:
        return ClientConfig("Claude Desktop", path, ConfigState.INVALID, str(exc))
    entry = (data.get("mcpServers") or {}).get(SERVER_KEY)
    return ClientConfig("Claude Desktop", path, _entry_state(entry, command))


def add_to_claude_desktop(command: list[str], path: Path | None = None) -> ClientConfig:
    """在 Claude Desktop 設定檔加入或更新 yt-media-tool；其他設定保留不動。"""
    path = path or claude_desktop_config_path()
    if path is None:
        raise ConfigError("沒有偵測到 Claude Desktop。")
    data = _read_claude_json(path)
    servers = data.setdefault("mcpServers", {})
    if _entry_state(servers.get(SERVER_KEY), command) is ConfigState.CONFIGURED:
        return ClientConfig("Claude Desktop", path, ConfigState.CONFIGURED)
    existing = servers.get(SERVER_KEY) if isinstance(servers.get(SERVER_KEY), dict) else {}
    servers[SERVER_KEY] = {**existing, "command": command[0], "args": command[1:]}
    _replace_file(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n", newline="\n")
    return ClientConfig("Claude Desktop", path, ConfigState.CONFIGURED)


def _entry_state(entry: object, command: list[str]) -> ConfigState:
    if entry is None:
        return ConfigState.NOT_CONFIGURED
    if isinstance(entry, dict) and entry.get("command") == command[0] and list(entry.get("args") or []) == command[1:]:
        return ConfigState.CONFIGURED
    return ConfigState.OUTDATED


# ---------------------------------------------------------------------------
# Codex（TOML）
# ---------------------------------------------------------------------------
_SECTION_HEADER = re.compile(
    r'^\s*\[\s*mcp_servers\s*\.\s*(?:yt-media-tool|"yt-media-tool"|\'yt-media-tool\')\s*\]\s*(#.*)?$')
_ANY_HEADER = re.compile(r"^\s*\[")


def _toml_string(value: str) -> str:
    if "'" not in value and "\n" not in value:
        return f"'{value}'"  # 字面字串：Windows 路徑的反斜線不必跳脫
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _codex_section(command: list[str]) -> list[str]:
    args = ", ".join(_toml_string(a) for a in command[1:])
    return [f"[mcp_servers.{SERVER_KEY}]", f"command = {_toml_string(command[0])}", f"args = [{args}]"]


def _read_codex(path: Path) -> tuple[str, dict]:
    if not path.is_file():
        return "", {}
    try:
        text = path.read_bytes().decode("utf-8-sig")  # 不用 read_text：要保留原本的換行字元（\r\n）
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"無法讀取設定檔：{exc}") from exc
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"設定檔不是正確的 TOML 格式（{exc}）") from exc
    servers = data.get("mcp_servers")
    if servers is not None and not isinstance(servers, dict):
        raise ConfigError("設定檔中的 mcp_servers 格式不正確")
    return text, data


def codex_status(command: list[str], path: Path | None = None) -> ClientConfig:
    path = path or codex_config_path()
    if path is None:
        return ClientConfig("Codex", None, ConfigState.NOT_FOUND)
    try:
        _, data = _read_codex(path)
    except ConfigError as exc:
        return ClientConfig("Codex", path, ConfigState.INVALID, str(exc))
    return ClientConfig("Codex", path, _entry_state((data.get("mcp_servers") or {}).get(SERVER_KEY), command))


def add_to_codex(command: list[str], path: Path | None = None) -> ClientConfig:
    """在 Codex 的 config.toml 加入或更新 [mcp_servers.yt-media-tool]；其他內容（含註解）保留不動。"""
    path = path or codex_config_path()
    if path is None:
        raise ConfigError("沒有偵測到 Codex。")
    text, data = _read_codex(path)
    entry = (data.get("mcp_servers") or {}).get(SERVER_KEY)
    if _entry_state(entry, command) is ConfigState.CONFIGURED:
        return ClientConfig("Codex", path, ConfigState.CONFIGURED)
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    section = _codex_section(command)
    start = next((i for i, line in enumerate(lines) if _SECTION_HEADER.match(line)), None)
    if entry is not None and start is None:
        # 以其他寫法定義（例如 inline table 或 dotted key），無法安全地只改這一項
        raise ConfigError(f"設定檔中已有 {SERVER_KEY}，但寫法無法自動更新，請手動修改。")
    if start is None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ([""] if lines else []) + section
    else:
        end = next((i for i in range(start + 1, len(lines)) if _ANY_HEADER.match(lines[i])), len(lines))
        # 只取代 command / args，保留這一段裡使用者自己加的其他設定（例如 env、startup_timeout_sec）
        kept = [line for line in lines[start + 1:end]
                if not re.match(r"^\s*(command|args)\s*=", line)]
        while kept and not kept[-1].strip():
            kept.pop()
        lines[start:end] = section + kept + ([""] if end < len(lines) else [])
    new_text = newline.join(lines) + newline
    try:
        check = tomllib.loads(new_text)["mcp_servers"][SERVER_KEY]
    except (tomllib.TOMLDecodeError, KeyError) as exc:
        raise ConfigError("無法自動更新設定檔，請手動修改。") from exc
    if _entry_state(check, command) is not ConfigState.CONFIGURED:
        raise ConfigError("無法自動更新設定檔，請手動修改。")
    _replace_file(path, new_text, newline="")
    return ClientConfig("Codex", path, ConfigState.CONFIGURED)


# ---------------------------------------------------------------------------
# 寫入：先備份，再以暫存檔取代
# ---------------------------------------------------------------------------
def backup_name(path: Path) -> Path:
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    candidate, counter = path.with_name(f"{path.name}.ytmt-backup-{stamp}"), 1
    while candidate.exists():  # 同一秒內按了兩次：不覆蓋先前的備份
        candidate, counter = path.with_name(f"{path.name}.ytmt-backup-{stamp}-{counter}"), counter + 1
    return candidate


def _replace_file(path: Path, text: str, newline: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            backup = backup_name(path)
            backup.write_bytes(path.read_bytes())
        temp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
        try:
            with temp.open("w", encoding="utf-8", newline=newline) as fh:
                fh.write(text)
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
    except OSError as exc:
        raise ConfigError(f"無法寫入設定檔：{exc.strerror or exc}") from exc
