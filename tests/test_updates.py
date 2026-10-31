"""新版本檢查（不連線網路，以假的 opener 模擬 GitHub API）。"""

import io
import json

import pytest

from yt_media_tool.core import updates


@pytest.mark.parametrize(("text", "expected"), [
    ("v2.4.0", (2, 4, 0)), ("2.10.1", (2, 10, 1)), (" v3.0.0 ", (3, 0, 0)),
    ("v2.4.0-beta.1", None), ("latest", None), ("", None), (None, None),
])
def test_parse_version(text, expected):
    assert updates.parse_version(text) == expected


def test_is_newer_compares_numbers_not_strings():
    assert updates.is_newer("2.10.0", "2.9.9")
    assert not updates.is_newer("2.3.0", "2.3.0")
    assert not updates.is_newer("2.2.9", "2.3.0")
    assert not updates.is_newer("garbage", "2.3.0")


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None


def test_fetch_latest_version_reads_tag_name():
    seen = {}

    def opener(request, timeout):
        seen["url"], seen["timeout"] = request.full_url, timeout
        seen["agent"] = request.get_header("User-agent")
        return _Response(json.dumps({"tag_name": "v9.8.7", "html_url": "https://evil.example"}).encode())

    assert updates.fetch_latest_version(timeout=5, opener=opener) == "9.8.7"
    assert seen["url"] == updates.LATEST_RELEASE_API and seen["timeout"] == 5
    assert seen["agent"].startswith("YT-Media-Tool/")


@pytest.mark.parametrize("payload", [{"tag_name": "nightly"}, {"message": "Not Found"}, ["x"]])
def test_fetch_latest_version_ignores_unexpected_payload(payload):
    assert updates.fetch_latest_version(opener=lambda request, timeout: _Response(json.dumps(payload).encode())) is None
