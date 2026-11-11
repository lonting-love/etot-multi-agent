"""报告结构校验：把「必须包含章节 / 至少 3 个可点击来源」变成可执行规则，而不是只靠 LLM 审核。"""

import re

URL_PATTERN = re.compile(r"https?://[^\s)\]>\"'，。；]+")
SECTION_ALIASES = {
    "背景": ("背景",),
    "现状": ("现状",),
    "趋势": ("趋势", "前景", "展望"),
    "参考来源": ("参考来源", "参考文献", "参考资料", "来源"),
}
MIN_REPORT_CHARS = 400
MIN_SOURCES = 3


def extract_urls(text: str) -> list[str]:
    seen, urls = set(), []
    for url in URL_PATTERN.findall(text or ""):
        cleaned = url.rstrip(".,;")
        if cleaned not in seen:
            seen.add(cleaned)
            urls.append(cleaned)
    return urls


def validate_report_structure(report: str) -> dict:
    report = report or ""
    issues: list[str] = []

    if len(report.strip()) < MIN_REPORT_CHARS:
        issues.append(f"报告正文过短（{len(report.strip())} 字符），内容不完整")

    for section, aliases in SECTION_ALIASES.items():
        if not any(alias in report for alias in aliases):
            issues.append(f"缺少「{section}」部分")

    urls = extract_urls(report)
    if len(urls) < MIN_SOURCES:
        issues.append(f"可点击来源只有 {len(urls)} 个，至少需要 {MIN_SOURCES} 个")

    return {
        "passed": not issues,
        "issues": issues,
        "stats": {"chars": len(report.strip()), "urls": len(urls)},
    }
