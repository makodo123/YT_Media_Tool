"""將 pytest JUnit XML 中的失敗轉為 GitHub Actions 註解（::error），方便直接在執行頁面查看。

用法：python scripts/junit_annotations.py test-results.xml
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET  # 只解析 CI 自己產生的檔案


def _escape(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "").replace("\n", "%0A")


def main(path: str) -> int:
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
