"""自動把 YT Media Tool 加入 Claude Desktop / Codex 的設定檔：偵測、合併、備份與格式錯誤時不修改。"""

import json
import tomllib

import pytest

from yt_media_tool.core import ai_clients
from yt_media_tool.core.ai_clients import ConfigError, ConfigState

EXE = r"C:\Users\王小明\AppData\Local\Programs\YT Media Tool\YT_Media_Tool.exe"
CMD = [EXE, "--mcp"]


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setattr(ai_clients.Path, "home", lambda: tmp_path / "home")
    return tmp_path


def backups(path):
    return sorted(path.parent.glob(f"{path.name}.ytmt-backup-*"))


# ---- 偵測 ----
def test_nothing_detected(home):
    assert ai_clients.claude_desktop_config_path() is None and ai_clients.codex_config_path() is None
    assert ai_clients.claude_desktop_status(CMD).state is ConfigState.NOT_FOUND
    assert ai_clients.codex_status(CMD).state is ConfigState.NOT_FOUND
    with pytest.raises(ConfigError, match="沒有偵測到"):
        ai_clients.add_to_claude_desktop(CMD)


def test_detects_regular_and_store_claude_desktop(home):
    store = home / "Local" / "Packages" / "Claude_pzs8sxrjxfjjc" / "LocalCache" / "Roaming" / "Claude"
    store.mkdir(parents=True)
    assert ai_clients.claude_desktop_config_path() == store / "claude_desktop_config.json"
    regular = home / "Roaming" / "Claude"
    regular.mkdir(parents=True)
    assert ai_clients.claude_desktop_config_path() == regular / "claude_desktop_config.json"  # 一般安裝版優先


def test_detects_codex_home(home, monkeypatch):
    (home / "home" / ".codex").mkdir(parents=True)
    assert ai_clients.codex_config_path() == home / "home" / ".codex" / "config.toml"
    custom = home / "codex-custom"
    custom.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(custom))
    assert ai_clients.codex_config_path() == custom / "config.toml"


# ---- Claude Desktop ----
def test_claude_desktop_creates_config_when_missing(home):
    (home / "Roaming" / "Claude").mkdir(parents=True)
    path = home / "Roaming" / "Claude" / "claude_desktop_config.json"
    assert ai_clients.claude_desktop_status(CMD).state is ConfigState.NOT_CONFIGURED
    assert ai_clients.add_to_claude_desktop(CMD).state is ConfigState.CONFIGURED
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "mcpServers": {"yt-media-tool": {"command": EXE, "args": ["--mcp"]}}}
    assert backups(path) == []  # 原本沒有檔案，不需要備份
    assert ai_clients.claude_desktop_status(CMD).state is ConfigState.CONFIGURED


def test_claude_desktop_keeps_other_settings_and_backs_up(home):
    folder = home / "Roaming" / "Claude"
    folder.mkdir(parents=True)
    path = folder / "claude_desktop_config.json"
    original = {"globalShortcut": "Ctrl+Space",
                "mcpServers": {"filesystem": {"command": "npx", "args": ["-y", "x"]}}}
    path.write_text("\ufeff" + json.dumps(original), encoding="utf-8")  # 記事本存的 UTF-8 BOM 也能讀
    ai_clients.add_to_claude_desktop(CMD)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["globalShortcut"] == "Ctrl+Space"
    assert data["mcpServers"]["filesystem"] == original["mcpServers"]["filesystem"]
    assert data["mcpServers"]["yt-media-tool"]["command"] == EXE
    assert [b.read_text(encoding="utf-8-sig") for b in backups(path)] == [json.dumps(original)]
    ai_clients.add_to_claude_desktop(CMD)  # 已加入：不再寫入、不再備份
    assert len(backups(path)) == 1


def test_claude_desktop_updates_outdated_path_and_keeps_env(home):
    folder = home / "Roaming" / "Claude"
    folder.mkdir(parents=True)
    path = folder / "claude_desktop_config.json"
    path.write_text(json.dumps({"mcpServers": {"yt-media-tool": {
        "command": r"D:\old\YT_Media_Tool.exe", "args": ["--mcp"], "env": {"A": "1"}}}}), encoding="utf-8")
    assert ai_clients.claude_desktop_status(CMD).state is ConfigState.OUTDATED
    ai_clients.add_to_claude_desktop(CMD)
    entry = json.loads(path.read_text(encoding="utf-8"))["mcpServers"]["yt-media-tool"]
    assert entry == {"command": EXE, "args": ["--mcp"], "env": {"A": "1"}}


@pytest.mark.parametrize("content", ['{"mcpServers": {', "[1, 2]", '{"mcpServers": []}'])
def test_claude_desktop_broken_file_is_not_touched(home, content):
    folder = home / "Roaming" / "Claude"
    folder.mkdir(parents=True)
    path = folder / "claude_desktop_config.json"
    path.write_text(content, encoding="utf-8")
    status = ai_clients.claude_desktop_status(CMD)
    assert status.state is ConfigState.INVALID and status.detail
    with pytest.raises(ConfigError):
        ai_clients.add_to_claude_desktop(CMD)
    assert path.read_text(encoding="utf-8") == content and backups(path) == []


# ---- Codex ----
def codex_file(home):
    folder = home / "home" / ".codex"
    folder.mkdir(parents=True)
    return folder / "config.toml"


def test_codex_appends_section_and_keeps_comments(home):
    path = codex_file(home)
    path.write_text('# 我的設定\nmodel = "gpt-5"\n\n[mcp_servers.other]\ncommand = "x"\n', encoding="utf-8")
    assert ai_clients.codex_status(CMD).state is ConfigState.NOT_CONFIGURED
    ai_clients.add_to_codex(CMD)
    text = path.read_text(encoding="utf-8")
    assert text.startswith('# 我的設定\nmodel = "gpt-5"\n')
    data = tomllib.loads(text)
    assert data["mcp_servers"]["yt-media-tool"] == {"command": EXE, "args": ["--mcp"]}
    assert data["mcp_servers"]["other"] == {"command": "x"} and data["model"] == "gpt-5"
    assert len(backups(path)) == 1
    assert ai_clients.codex_status(CMD).state is ConfigState.CONFIGURED


def test_codex_creates_file_and_handles_quotes(home):
    path = codex_file(home)
    odd = [r"C:\Users\O'Brien\YT_Media_Tool.exe", "--mcp"]
    ai_clients.add_to_codex(odd)
    assert tomllib.loads(path.read_text(encoding="utf-8"))["mcp_servers"]["yt-media-tool"]["command"] == odd[0]


def test_codex_updates_existing_section_keeping_other_keys_and_crlf(home):
    path = codex_file(home)
    path.write_bytes(b"[mcp_servers.yt-media-tool]\r\ncommand = 'D:\\old.exe'\r\nargs = [\"--mcp\"]\r\n"
                     b"startup_timeout_sec = 20\r\n\r\n[profiles.work]\r\nmodel = \"o3\"\r\n")
    assert ai_clients.codex_status(CMD).state is ConfigState.OUTDATED
    ai_clients.add_to_codex(CMD)
    raw = path.read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")  # 保留 Windows 換行
    data = tomllib.loads(raw.decode("utf-8"))
    assert data["mcp_servers"]["yt-media-tool"] == {"command": EXE, "args": ["--mcp"], "startup_timeout_sec": 20}
    assert data["profiles"]["work"] == {"model": "o3"}


def test_codex_unusual_definition_is_not_rewritten(home):
    path = codex_file(home)
    content = 'mcp_servers = { "yt-media-tool" = { command = "D:/old.exe" } }\n'
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError, match="手動修改"):
        ai_clients.add_to_codex(CMD)
    assert path.read_text(encoding="utf-8") == content


def test_codex_broken_file_is_not_touched(home):
    path = codex_file(home)
    path.write_text("[mcp_servers\n", encoding="utf-8")
    assert ai_clients.codex_status(CMD).state is ConfigState.INVALID
    with pytest.raises(ConfigError, match="TOML"):
        ai_clients.add_to_codex(CMD)
    assert path.read_text(encoding="utf-8") == "[mcp_servers\n"


def test_claude_code_command_quotes_paths_with_spaces():
    assert ai_clients.claude_code_command(CMD) == f'claude mcp add --scope user yt-media-tool -- "{EXE}" --mcp'
