import unittest

from modules.validation import extract_urls, validate_report_structure


GOOD_REPORT = """# 人形机器人商业化调研

## 背景
人形机器人正从实验室走向量产，2025-2026 年多家厂商公布量产计划。

## 现状
- 供应链成本下降，单机成本从 50 万降至 20 万区间，核心零部件国产化率明显提升。
- 头部厂商开始小批量交付工厂场景，主要承担搬运、质检与分拣等重复性任务。
- 政策端持续加码，多地发布具身智能行动方案，把整机与零部件企业纳入重点扶持范围。
- 资本侧融资节奏放缓但单笔金额上升，资金更集中地流向已具备量产能力的团队。

## 趋势
未来三年将先在工业场景放量，再进入商业服务与家庭场景。判断依据是工业场景任务边界清晰、容错空间较大，
而家庭场景对安全性和泛化能力要求更高，通常滞后一到两个产品周期。

## 参考来源
1. https://example.com/robot-1
2. https://example.com/robot-2
3. https://example.com/robot-3
"""


class ValidationTests(unittest.TestCase):
    def test_complete_report_passes(self):
        result = validate_report_structure(GOOD_REPORT)
        self.assertTrue(result["passed"], result["issues"])
        self.assertEqual(result["stats"]["urls"], 3)

    def test_missing_section_fails(self):
        report = GOOD_REPORT.replace("## 趋势", "## 其他")
        result = validate_report_structure(report)
        self.assertFalse(result["passed"])
        self.assertTrue(any("趋势" in issue for issue in result["issues"]))

    def test_too_few_sources_fails(self):
        report = GOOD_REPORT.replace("3. https://example.com/robot-3", "")
        result = validate_report_structure(report)
        self.assertFalse(result["passed"])
        self.assertTrue(any("来源" in issue for issue in result["issues"]))

    def test_short_report_fails(self):
        self.assertFalse(validate_report_structure("太短了")["passed"])

    def test_quoted_failure_marker_does_not_fail_complete_report(self):
        report = GOOD_REPORT.replace("## 现状", "> 检索说明：现已重新检索，不再出现「未检索到有效来源」。\n\n## 现状")
        self.assertTrue(validate_report_structure(report)["passed"])

    def test_extract_urls_dedupes(self):
        text = "https://a.com/x https://a.com/x https://b.com/y"
        self.assertEqual(extract_urls(text), ["https://a.com/x", "https://b.com/y"])


if __name__ == "__main__":
    unittest.main()
