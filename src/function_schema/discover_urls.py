"""
Discover URLs Tool
Path: function_schema/discover_urls.py

Finds web sources for a given subject using multiple search engines
and Wikipedia deep-crawl. Returns a deduplicated, prioritised URL list.

Standalone test:
    python function_schema/discover_urls.py "Marie Curie" 20
"""

import time
import re
from urllib.parse import quote_plus, urlparse
from typing import List

import requests
from bs4 import BeautifulSoup


TRUSTED_DOMAINS = [
    "en.wikipedia.org", "britannica.com", "bbc.co.uk",
    "theguardian.com", "nytimes.com", "theatlantic.com",
    "smithsonianmag.com", "history.com", "biography.com",
    "sciencedaily.com", "nature.com", "pubmed.ncbi.nlm.nih.gov",
]

BLOCKED_DOMAINS = [
    "facebook.com", "twitter.com", "instagram.com", "tiktok.com",
    "youtube.com", "reddit.com", "pinterest.com", "amazon.com",
    "ebay.com", "etsy.com",
]

SEARCH_ENGINES = [
    "https://www.google.com/search?q={query}&num=10",
    "https://www.bing.com/search?q={query}&count=10",
]

REQUEST_DELAY = 1.2


class DiscoverUrls:

    def __init__(self):
        self.name = "discover_urls"
        self.description = (
            "Finds web source URLs for a given subject using search engines "
            "and Wikipedia deep-crawl. Call with subject (str) and limit (int). "
            "Returns a JSON list of URLs prioritised by source quality."
        )
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"
        })

    def execute(self, subject: str, limit: int = 50) -> str:
        import json
        urls = self._collect(subject, limit)
        return json.dumps(urls)

    def _collect(self, subject: str, limit: int) -> List[str]:
        seen, urls = set(), []

        # Search engines
        queries = [
            subject,
            f"{subject} biography",
            f"{subject} philosophy beliefs",
            f"{subject} interviews quotes",
            f"{subject} key events",
        ]
        for query in queries:
            for engine in SEARCH_ENGINES:
                for url in self._search(query, engine):
                    if url not in seen and self._allowed(url):
                        seen.add(url)
                        urls.append(url)
                time.sleep(REQUEST_DELAY)

        # Wikipedia deep-crawl
        wiki_url = f"https://en.wikipedia.org/wiki/{quote_plus(subject.replace(' ', '_'))}"
        for url in self._wiki_links(wiki_url):
            if url not in seen:
                seen.add(url)
                urls.append(url)

        # Trusted domains first
        trusted  = [u for u in urls if any(d in u for d in TRUSTED_DOMAINS)]
        fallback = [u for u in urls if u not in trusted]
        return (trusted + fallback)[:limit]

    def _search(self, query: str, engine: str) -> List[str]:
        try:
            resp = self.session.get(engine.format(query=quote_plus(query)), timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/url?q=" in href:
                    href = href.split("/url?q=")[1].split("&")[0]
                if href.startswith("http") and self._allowed(href):
                    links.append(href)
            return links[:10]
        except Exception:
            return []

    def _wiki_links(self, wiki_url: str) -> List[str]:
        try:
            resp = self.session.get(wiki_url, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            content = soup.find("div", {"id": "mw-content-text"})
            if not content:
                return []
            links = []
            for a in content.find_all("a", href=True):
                href = a["href"]
                if href.startswith("/wiki/") and ":" not in href:
                    links.append("https://en.wikipedia.org" + href)
            return list(dict.fromkeys(links))[:30]
        except Exception:
            return []

    def _allowed(self, url: str) -> bool:
        if not url.startswith("http"):
            return False
        domain = urlparse(url).netloc.lower()
        if any(b in domain for b in BLOCKED_DOMAINS):
            return False
        if any(url.lower().endswith(e) for e in [".pdf", ".jpg", ".png", ".zip"]):
            return False
        return True


if __name__ == "__main__":
    import sys, json
    subject = sys.argv[1] if len(sys.argv) > 1 else "Marie Curie"
    limit   = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    tool    = DiscoverUrls()
    result  = json.loads(tool.execute(subject=subject, limit=limit))
    print(f"Found {len(result)} URLs:")
    for u in result[:10]:
        print(f"  {u}")