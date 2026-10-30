"""將 pytest JUnit XML 中的失敗轉為 GitHub Actions 註解（::error），方便直接在執行頁面查看。

用法：python scripts/junit_annotations.py test-results.xml
"""

from __future__ import annotations

import sys
from pathlib import Path
import xml.etree.ElementTree as ET  # 只解析 CI 自己產生的檔案


def _escape(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "").replace("\n", "%0A")


def main(path: str) -> int:
    if not Path(path).is_file():
        # 測試尚未執行就失敗（例如標籤格式錯誤）時沒有結果檔，不應再額外回報失敗
        print(f"找不到 {path}，略過（測試可能尚未執行）")
        return 0
    root = ET.parse(path).getroot()  # noqa: S314
    count = 0
    for case in root.iter("testcase"):
        for problem in list(case.findall("failure")) + list(case.findall("error")):
            name = f"{case.get('classname')}::{case.get('name')}"
            detail = (problem.text or problem.get("message") or "")[-3000:]
            print(f"::error title={_escape(name)}::{_escape(detail)}")
            count += 1
    print(f"共 {count} 個失敗 / 錯誤")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "test-results.xml"))
