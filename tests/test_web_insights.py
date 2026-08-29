from __future__ import annotations

import os
import unittest

from src.web_insights import (
    WebInsightError, allowed_domains, article_to_markdown,
    extract_article_html, extract_public_payload, validate_public_resource_url,
    validate_source_url,
)


SAMPLE_HTML = """
<html>
  <head>
    <title>Healthy Eating Evidence</title>
    <meta name="description" content="A compact public-health nutrition summary.">
    <script>ignore me</script>
  </head>
  <body>
    <nav>This navigation sentence should never enter the extracted article preview.</nav>
    <main>
      <h1>Healthy Eating Evidence</h1>
      <p>Vegetables, fruit, legumes and whole grains can support a balanced dietary pattern for many adults.</p>
      <p>Individual requirements still depend on age, health status, allergies, medicines and professional assessment.</p>
    </main>
  </body>
</html>
"""


class WebInsightTests(unittest.TestCase):
    def test_allowlist_rejects_local_and_untrusted_urls(self) -> None:
        with self.assertRaises(WebInsightError):
            validate_source_url("http://127.0.0.1/private")
        with self.assertRaises(WebInsightError):
            validate_source_url("https://untrusted.example/article")
        accepted = validate_source_url("https://www.who.int/news-room/fact-sheets/detail/healthy-diet#section")
        self.assertFalse(accepted.endswith("#section"))

    def test_environment_can_extend_allowlist(self) -> None:
        previous = os.environ.get("NUTRIPULSE_SCRAPER_DOMAINS")
        os.environ["NUTRIPULSE_SCRAPER_DOMAINS"] = "nutrition.example.edu"
        try:
            self.assertIn("nutrition.example.edu", allowed_domains())
            self.assertTrue(validate_source_url("https://nutrition.example.edu/article"))
        finally:
            if previous is None:
                os.environ.pop("NUTRIPULSE_SCRAPER_DOMAINS", None)
            else:
                os.environ["NUTRIPULSE_SCRAPER_DOMAINS"] = previous

    def test_html_extraction_and_markdown_export(self) -> None:
        article = extract_article_html(SAMPLE_HTML, "https://www.who.int/example")
        self.assertEqual(article["title"], "Healthy Eating Evidence")
        self.assertEqual(article["paragraph_count"], 2)
        self.assertNotIn("navigation", " ".join(article["paragraphs"]).lower())
        markdown = article_to_markdown(article)
        self.assertTrue(markdown.startswith(b"# Healthy Eating Evidence"))
        self.assertIn(b"https://www.who.int/example", markdown)

    def test_public_api_validation_and_json_preview(self) -> None:
        self.assertEqual(
            validate_public_resource_url("https://api.example.org/v1/foods?q=apple#top"),
            "https://api.example.org/v1/foods?q=apple",
        )
        with self.assertRaises(WebInsightError):
            validate_public_resource_url("http://127.0.0.1/private")
        result = extract_public_payload(
            b'{"items":[{"food":"apple","calories":52}],"api_token":"do-not-show"}',
            "https://api.example.org/v1/foods", "application/json",
        )
        self.assertEqual(result["resource_type"], "json-api")
        self.assertEqual(result["record_count"], 1)
        self.assertEqual(result["data_preview"]["api_token"], "[redacted]")


if __name__ == "__main__":
    unittest.main()
