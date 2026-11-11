"""调研质量评测：逐题调用 /research，检查结构、来源数与关键词覆盖。

用法：
    python eval/run_eval.py --base http://127.0.0.1:8000 --limit 1
"""

import argparse
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from modules.validation import validate_report_structure  # noqa: E402


def run_case(base: str, case: dict, timeout: float, api_key: str) -> dict:
    headers = {"X-API-Key": api_key} if api_key else {}
    started = time.monotonic()
    error = ""
    data = {}
    try:
        response = requests.post(
            f"{base}/research",
            json={"topic": case["topic"], "session_id": uuid.uuid4().hex},
            headers=headers,
            timeout=timeout,
        )
        if response.status_code != 200:
            error = f"HTTP {response.status_code}: {response.text[:200]}"
        else:
            data = response.json()
    except Exception as exc:  # noqa: BLE001 - 评测记录全部失败
        error = str(exc)

    report = data.get("report", "")
    checks = validate_report_structure(report)
    keywords = case.get("expect_any") or []
    keyword_ok = not keywords or any(word in report for word in keywords)
    ok = not error and checks["passed"] and keyword_ok

    return {
        "id": case["id"],
        "topic": case["topic"],
        "ok": ok,
        "error": error,
        "keyword_ok": keyword_ok,
        "structure": checks,
        "rounds": data.get("rounds"),
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "trace_id": data.get("trace_id"),
        "report_preview": report[:300],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--min-pass", type=float, default=0.0)
    parser.add_argument("--topics", type=Path, default=ROOT / "topics.jsonl")
    args = parser.parse_args()

    cases = [json.loads(line) for line in args.topics.read_text(encoding="utf-8").splitlines() if line.strip()]
    cases = cases[: max(1, args.limit)]
    results = [run_case(args.base, case, args.timeout, args.api_key) for case in cases]

    for item in results:
        status = "PASS" if item["ok"] else "FAIL"
        print(f"[{status}] {item['id']} {item['topic']} ({item['elapsed_ms']}ms, {item['rounds']} 轮)")
        if not item["ok"]:
            print(f"       error={item['error'] or '-'} issues={item['structure']['issues']} keyword_ok={item['keyword_ok']}")

    passed = sum(1 for item in results if item["ok"])
    rate = passed / len(results) if results else 0.0
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(results),
        "passed": passed,
        "pass_rate": round(rate, 4),
        "results": results,
    }
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    path = reports / f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n通过 {passed}/{len(results)} = {rate:.1%}，报告: {path}")
    return 0 if rate >= args.min_pass else 1


if __name__ == "__main__":
    sys.exit(main())
