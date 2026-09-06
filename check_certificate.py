"""Check the course-level certificate status; notify once when ready."""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

COURSE_URL = "https://train.csie.ntu.edu.tw/school/news/certificate.php?id=6250"
COURSE_TITLE = "第479期：AI 時代的 Python 程式設計基礎實務"
TOPIC = "aip479cert"
READY = "已可領取證書"


def parse_status(html: str, expected_title: str = COURSE_TITLE) -> str:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one("main .page .view > .headline")
    summaries = soup.select("main .page .view > summary")
    if title is None or title.get_text(" ", strip=True) != expected_title:
        raise ValueError("找不到預期的課程標題，請檢查網址或網站版型")
    if len(summaries) != 1:
        raise ValueError("找不到唯一的課程證書狀態")
    status = summaries[0].get_text(" ", strip=True)
    if not status:
        raise ValueError("課程證書狀態是空白")
    return status


def fetch_page() -> str:
    request = Request(COURSE_URL, headers={"User-Agent": "NTU-Certificate-Monitor/0.1"})
    with urlopen(request, timeout=30) as response:
        if response.url != COURSE_URL:
            raise ValueError(f"課程頁面發生非預期轉址：{response.url}")
        return response.read().decode("utf-8")


def notify() -> None:
    payload = {
        "topic": TOPIC,
        "title": "第479期 Python 課程已可領取證書",
        "message": f"{COURSE_TITLE}\n官網狀態：{READY}\n{COURSE_URL}",
        "click": COURSE_URL,
        "tags": ["mortar_board"],
    }
    request = Request(
        "https://ntfy.sh",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    if result.get("event") != "message" or result.get("topic") != TOPIC or not result.get("id"):
        raise ValueError("ntfy 未回傳有效的通知收據")


def check(state_file: Path, *, dry_run: bool = False) -> None:
    receipt = {"url": COURSE_URL, "topic": TOPIC, "notified": False}
    if state_file.exists():
        receipt = json.loads(state_file.read_text(encoding="utf-8"))
        if (receipt.get("url") != COURSE_URL or receipt.get("topic") != TOPIC
                or type(receipt.get("notified")) is not bool):
            raise ValueError("通知紀錄不符合目前設定")
    run_url = None
    if os.environ.get("GITHUB_RUN_ID"):
        run_url = (f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
                   f"{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}")
    record = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "run_url": run_url,
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "status": None,
        "result": "error",
        "notified_this_run": False,
        "error": None,
    }
    if not dry_run:
        state_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        status = parse_status(fetch_page())
        record["status"] = status
        print(f"{COURSE_TITLE}：{status}")
        if status == READY and not receipt["notified"]:
            if dry_run:
                print(f"[dry-run] 將通知 https://ntfy.sh/{TOPIC}，本次不發送。")
            else:
                notify()
                receipt["notified"] = True
                receipt["notified_at"] = datetime.now(timezone.utc).isoformat()
                record["notified_this_run"] = True
                print(f"已通知 https://ntfy.sh/{TOPIC}")
        record["result"] = "success"
    except (OSError, ValueError) as exc:
        record["error"] = str(exc)
        raise
    finally:
        if not dry_run:
            receipt["last_check"] = record
            temporary = state_file.with_suffix(".tmp")
            temporary.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temporary.replace(state_file)
            with state_file.with_name("history.jsonl").open("a", encoding="utf-8") as history:
                history.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只查詢，不通知也不寫入紀錄")
    parser.add_argument("--state-file", type=Path, default=Path(".state/status.json"))
    args = parser.parse_args()
    try:
        check(args.state_file, dry_run=args.dry_run)
    except (OSError, ValueError) as exc:
        print(f"檢查失敗：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
