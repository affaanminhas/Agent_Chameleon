"""
Discover URLs Tool
Path: src/function_schema/discover_urls.py

Uses a hybrid approach:
- Hardcoded seed URLs for known reliable quote/interview sources
- Wikipedia API for topic-specific article discovery
- Wikipedia deep-crawl for general fallback content
"""

import time
import json
from urllib.parse import quote_plus, urlparse, unquote
from typing import List, Dict

import requests
from bs4 import BeautifulSoup


TOPICS = [
    "career",
    "early life family",
    "philosophy beliefs",
    "mental health struggles",
    "relationships",
    "failures setbacks",
    "personal life",
    "legacy impact",
    "creative process",
    "on death meaning",
]

QUOTE_SEED_TEMPLATES = [
    "https://en.wikiquote.org/wiki/{subject_underscore}",
    "https://www.brainyquote.com/authors/{subject_slug}-quotes",
    "https://www.goodreads.com/author/quotes/{subject_underscore}",
    "https://azquotes.com/author/{subject_underscore}.html",
]

FALLBACK_DOMAINS = [
    "en.wikipedia.org", "britannica.com", "biography.com",
    "history.com", "smithsonianmag.com", "bbc.co.uk",
]

BLOCKED_DOMAINS = [
    "facebook.com", "twitter.com", "instagram.com", "tiktok.com",
    "youtube.com", "pinterest.com", "amazon.com", "ebay.com",
    "google.com", "bing.com", "yahoo.com", "duckduckgo.com",
]

REQUEST_DELAY = 0.8


class DiscoverUrls:

    def __init__(self):
        self.name = "discover_urls"
        self.description = (
            "Finds web source URLs for a given subject organised by topic and "
            "source type (quotes, interviews, fallback). Uses direct seed URLs "
            "for quotes, Wikipedia API for topic discovery, and Wikipedia "
            "deep-crawl for fallback content. "
            "Call with subject (str), limit (int), target_pairs (int). "
            "Returns JSON list of {url, source_type, topic} objects."
        )
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def execute(self, subject: str, limit: int = 60, target_pairs: int = 100) -> str:
        results = self._collect(subject, limit, target_pairs)
        return json.dumps(results)

    def _collect(self, subject: str, limit: int, target_pairs: int) -> List[Dict]:
        seen       = set()
        quotes     = []
        interviews = []
        fallback   = []

        subject_underscore = subject.replace(" ", "_")
        subject_slug       = subject.lower().replace(" ", "-")

        print("  Finding quote sources...")
        for tmpl in QUOTE_SEED_TEMPLATES:
            url = tmpl.format(subject_underscore=subject_underscore, subject_slug=subject_slug)
            if url not in seen and self._allowed(url):
                seen.add(url)
                quotes.append({"url": url, "source_type": "quote", "topic": "general"})

        print(f"  Searching Wikipedia for {len(TOPICS)} topics...")
        for topic in TOPICS:
            query = f"{subject} {topic}"
            results = self._wikipedia_search(query, limit=3)
            for url in results:
                if url not in seen and self._allowed(url):
                    seen.add(url)
                    if subject_underscore.lower() in url.lower():
                        interviews.append({"url": url, "source_type": "interview", "topic": topic})
                    else:
                        fallback.append({"url": url, "source_type": "fallback", "topic": topic})
            time.sleep(REQUEST_DELAY)

        print("  Deep-crawling Wikipedia...")
        wiki_main = f"https://en.wikipedia.org/wiki/{subject_underscore}"
        for url in self._wiki_links(wiki_main):
            if url not in seen:
                seen.add(url)
                fallback.append({"url": url, "source_type": "fallback", "topic": "general"})

        extra_sources = [
            (f"https://www.britannica.com/biography/{subject_slug}", "fallback", "general"),
            (f"https://www.biography.com/people/{subject_slug}", "fallback", "general"),
            (f"https://www.history.com/topics/{subject_slug}", "fallback", "general"),
        ]
        for url, stype, topic in extra_sources:
            if url not in seen:
                seen.add(url)
                fallback.append({"url": url, "source_type": stype, "topic": topic})

        all_results = quotes + interviews + self._prioritise(fallback, FALLBACK_DOMAINS)
        print(f"  Total — quotes: {len(quotes)}  interviews: {len(interviews)}  fallback: {len(fallback)}")
        return all_results[:limit]

    def _wikipedia_search(self, query: str, limit: int = 3) -> List[str]:
        try:
            resp = self.session.get(
                "https://en.wikipedia.org/w/api.php",
                params={"action": "opensearch", "search": query, "limit": limit, "format": "json", "namespace": 0},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                urls = data[3] if len(data) > 3 else []
                return [u for u in urls if u.startswith("http")]
        except Exception as e:
            print(f"    Wikipedia search error: {e}")
        return []

    def _wiki_links(self, wiki_url: str) -> List[str]:
        try:
            resp    = self.session.get(wiki_url, timeout=10)
            soup    = BeautifulSoup(resp.text, "html.parser")
            content = soup.find("div", {"id": "mw-content-text"})
            if not content:
                return []
            links = []
            for a in content.find_all("a", href=True):
                href = a["href"]
                if href.startswith("/wiki/") and ":" not in href:
                    links.append("https://en.wikipedia.org" + href)
            return list(dict.fromkeys(links))[:40]
        except Exception:
            return []

    def _prioritise(self, items: List[Dict], trusted: List[str]) -> List[Dict]:
        trusted_items = [i for i in items if any(d in i["url"] for d in trusted)]
        other_items   = [i for i in items if i not in trusted_items]
        return trusted_items + other_items

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
    import sys
    subject      = sys.argv[1] if len(sys.argv) > 1 else "Steve Jobs"
    limit        = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    target_pairs = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    tool    = DiscoverUrls()
    results = json.loads(tool.execute(subject=subject, limit=limit, target_pairs=target_pairs))
    quotes     = [r for r in results if r["source_type"] == "quote"]
    interviews = [r for r in results if r["source_type"] == "interview"]
    fallback   = [r for r in results if r["source_type"] == "fallback"]
    print(f"\nFinal — {len(results)} URLs:")
    print(f"  Quotes     : {len(quotes)}")
    print(f"  Interviews : {len(interviews)}")
    print(f"  Fallback   : {len(fallback)}")
    for r in results[:20]:
        print(f"  [{r['source_type']:10}] [{r['topic']:20}] {r['url'][:65]}")
