"""
Scrape URL Tool
Path: src/function_schema/scrape_url.py
"""

import re
import json
from typing import Optional

import requests
from bs4 import BeautifulSoup


class ScrapeUrl:

    def __init__(self):
        self.name = "scrape_url"
        self.description = (
            "Fetches a URL and returns clean text with source_type detection. "
            "Applies quote extraction for quote sites, interview extraction for "
            "transcript pages, general extraction for everything else. "
            "Call with url (str) and source_type (str: quote/interview/fallback). "
            "Returns JSON: {text, source_type, url}"
        )
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"
        })

    def execute(self, url: str, source_type: str = "fallback") -> str:
        text = self._fetch(url, source_type)
        return json.dumps({
            "text": text or "",
            "source_type": source_type,
            "url": url
        })

    def _fetch(self, url: str, source_type: str) -> Optional[str]:
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                return None
            if "text/html" not in resp.headers.get("Content-Type", ""):
                return None

            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header",
                              "aside", "form", "button", "noscript", "iframe"]):
                tag.decompose()

            if source_type == "quote":
                return self._extract_quotes(soup, url)
            elif source_type == "interview":
                return self._extract_interview(soup)
            else:
                return self._extract_general(soup)

        except Exception:
            return None

    def _extract_quotes(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        quotes = []

        if "wikiquote.org" in url:
            content = soup.find("div", {"class": "mw-parser-output"})
            if content:
                for li in content.find_all("li"):
                    text = li.get_text(strip=True)
                    if len(text.split()) > 5 and len(text) < 600:
                        quotes.append(text)

        elif "brainyquote.com" in url:
            for el in soup.find_all(class_=re.compile(r"b-qt|grid-item")):
                text = el.get_text(strip=True)
                if len(text.split()) > 5:
                    quotes.append(text)

        elif "goodreads.com" in url:
            for el in soup.find_all(class_=re.compile(r"quoteText|quote")):
                text = el.get_text(strip=True)
                text = re.sub(r"―.*$", "", text).strip()
                if len(text.split()) > 5:
                    quotes.append(text)

        if not quotes:
            for bq in soup.find_all("blockquote"):
                text = bq.get_text(strip=True)
                if len(text.split()) > 5:
                    quotes.append(text)

        if not quotes:
            return None

        cleaned = []
        for q in quotes:
            q = re.sub(r"\[\d+\]", "", q).strip('" \'"\'')
            if len(q.split()) >= 8:
                cleaned.append(q)

        return "\n\n".join(cleaned) if cleaned else None

    def _extract_interview(self, soup: BeautifulSoup) -> Optional[str]:
        content = (
            soup.find("article") or
            soup.find("main") or
            soup.find("div", {"class": re.compile(r"content|article|body|interview", re.I)}) or
            soup.find("body")
        )
        if not content:
            return None
        return self._clean(content.get_text(separator="\n"), preserve_structure=True)

    def _extract_general(self, soup: BeautifulSoup) -> Optional[str]:
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

    def _clean(self, text: str, preserve_structure: bool = False) -> str:
        text = re.sub(r"\[\d+\]", "", text)
        text = re.sub(r"\[edit\]", "", text)
        text = re.sub(r"={2,}.*?={2,}", "", text)
        text = re.sub(r"\{\{.*?\}\}", "", text)
        text = re.sub(r"\[\[.*?\]\]", "", text)

        lines = [l.strip() for l in text.splitlines()]
        min_len = 5 if preserve_structure else 20
        lines = [
            l for l in lines
            if len(l) > min_len
            and not re.match(
                r"^(jump to|contents|navigation|search|menu|cookie|subscribe|sign in|advertisement)",
                l.lower()
            )
        ]
        return "\n".join(lines)


if __name__ == "__main__":
    import sys
    url         = sys.argv[1] if len(sys.argv) > 1 else "https://en.wikiquote.org/wiki/Steve_Jobs"
    source_type = sys.argv[2] if len(sys.argv) > 2 else "quote"
    tool        = ScrapeUrl()
    result      = json.loads(tool.execute(url=url, source_type=source_type))
    print(f"Source type : {result['source_type']}")
    print(f"Characters  : {len(result['text'])}")
    print(result["text"][:600])