import unittest

import modules.search_tool as search_module
from modules.search_tool import web_search


class SearchToolTests(unittest.TestCase):
    def setUp(self):
        self.original = search_module._providers

    def tearDown(self):
        search_module._providers = self.original

    def use_provider(self, handler):
        search_module._providers = lambda: [("fake", handler)]

    def invoke(self, query="具身智能"):
        return web_search.invoke({"query": query, "max_results": 5})

    def test_formats_results(self):
        self.use_provider(
            lambda q, n: [
                {"title": "标题A", "url": "https://a.com/1", "snippet": "摘要A", "date": "2026-01-01"},
                {"title": "标题B", "url": "https://b.com/2", "snippet": "摘要B", "date": ""},
            ]
        )
        result = self.invoke()
        self.assertIn("共找到 2 条结果", result)
        self.assertIn("https://a.com/1", result)
        self.assertIn("来源: fake", result)

    def test_invalid_and_duplicate_urls_removed(self):
        self.use_provider(
            lambda q, n: [
                {"title": "A", "url": "https://a.com/1", "snippet": "", "date": ""},
                {"title": "A2", "url": "https://a.com/1", "snippet": "", "date": ""},
                {"title": "bad", "url": "javascript:alert(1)", "snippet": "", "date": ""},
            ]
        )
        result = self.invoke()
        self.assertIn("共找到 1 条结果", result)
        self.assertNotIn("javascript", result)

    def test_provider_error_falls_back_to_message(self):
        def boom(q, n):
            raise RuntimeError("quota exceeded")

        self.use_provider(boom)
        result = self.invoke()
        self.assertIn("未检索到有效来源", result)
        self.assertIn("fake", result)

    def test_empty_query_rejected(self):
        self.assertIn("搜索词为空", self.invoke(query="   "))


if __name__ == "__main__":
    unittest.main()
