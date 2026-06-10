"""
Scrape URL Tool
Path: function_schema/scrape_url.py

Fetches a URL and extracts clean body text. Strips nav, ads,
scripts, and wiki markup artifacts.

Standalone test:
    python function_schema/scrape_url.py "https://en.wikipedia.org/wiki/Marie_Curie"
"""

import re
from typing import Optional

import requests
from bs4 import BeautifulSoup


class ScrapeUrl:

    def __init__(self):
        self.name = "scrape_url"
        self.description = (
            "Fetches a URL and returns clean body text with markup, "
            "navigation, ads, and scripts removed. "
            "Call with url (str). Returns cleaned text string."
        )
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"
        })

    def execute(self, url: str) -> str:
        text = self._fetch(url)
        if not text:
            return ""
        return text

    def _fetch(self, url: str) -> Optional[str]:
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                return None
            if "text/html" not in resp.headers.get("Content-Type", ""):
                return None

            soup = BeautifulSoup(resp.text, "html.parser")

            for tag in soup(["script", "style", "nav", "footer", "header",
                              "aside", "form", "button", "noscript",
                              "figure", "figcaption", "iframe"]):
                tag.decompose()

            content = (
                soup.find("article") or
                soup.find("main") or
                soup.find("div", {"id": "mw-content-text"}) or
                soup.find("div", {"class": re.compile(r"content|article|body", re.I)}) or
                soup.find("body")
            )

            if not content:
                return None

            return self._clean(content.get_text(separator="\n"))

        except Exception:
            return None

    def _clean(self, text: str) -> str:
        # Remove wiki markup artifacts
        text = re.sub(r"\[\d+\]", "", text)
        text = re.sub(r"\[edit\]", "", text)
        text = re.sub(r"={2,}.*?={2,}", "", text)
        text = re.sub(r"\{\{.*?\}\}", "", text)
        text = re.sub(r"\[\[.*?\]\]", "", text)

        # Normalise whitespace, drop short/noisy lines
        lines = [l.strip() for l in text.splitlines()]
        lines = [
            l for l in lines
            if len(l) > 20
            and not re.match(
                r"^(jump to|contents|navigation|search|menu|cookie|subscribe|sign in)",
                l.lower()
            )
        ]
        return "\n".join(lines)


if __name__ == "__main__":
    import sys
    url  = sys.argv[1] if len(sys.argv) > 1 else "https://en.wikipedia.org/wiki/Marie_Curie"
    tool = ScrapeUrl()
    text = tool.execute(url=url)
    print(f"Scraped {len(text)} characters")
    print(text[:500])