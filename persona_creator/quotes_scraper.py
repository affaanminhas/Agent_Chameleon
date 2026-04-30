"""
Quotes Scraper
Path: src/Agent/persona/quotes_scraper.py

Scrapes categorised quotes from allaboutstevejobs.com/verbatim/quotes
and formats them as clean consistent training pairs.

Format:
    instruction: "You are Steve Jobs. Respond as Steve Jobs."
    input:       "Tell me about {category}."
    output:      the quote

Usage:
    python quotes_scraper.py
"""

import re
import json
import requests
from collections import Counter
from typing import List, Dict


QUOTES_URL = "https://allaboutstevejobs.com/verbatim/quotes"

KNOWN_CATEGORIES = [
    "Management",
    "Creativity",
    "Apple",
    "Competitors",
    "Philosophy",
    "Technology",
    "Early years",
    "Family",
    "Lifestyle",
    "Pixar",
    "Prophecies",
]


class QuotesScraper:

    def __init__(self, persona: str = "Steve Jobs"):
        self.persona = persona
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def scrape(self) -> List[Dict]:
        print(f"📄 Fetching: {QUOTES_URL}")
        resp = self.session.get(QUOTES_URL, timeout=20)
        if resp.status_code != 200:
            print(f"⚠️  HTTP {resp.status_code}")
            return []

        pairs = self._parse(resp.text)
        print(f"✅ {len(pairs)} training pairs extracted")
        return pairs

    def _parse(self, html: str) -> List[Dict]:
        pairs = []
        seen = set()

        # Split on each blockquote
        blocks = re.split(r'<blockquote[^>]*>', html)[1:]

        for block in blocks:
            match = re.match(r'(.*?)</blockquote>(.*?)(?=<blockquote|$)', block, re.DOTALL)
            if not match:
                continue

            quote_raw = match.group(1)
            after_raw = match.group(2)

            # Clean quote — remove source citation inside blockquote
            quote_raw = re.sub(r'<cite[^>]*>.*?</cite>', '', quote_raw, flags=re.DOTALL)
            quote_raw = re.sub(r'<[^>]+>', '', quote_raw)
            quote_text = self._decode(quote_raw).strip()

            if not quote_text or len(quote_text) < 20:
                continue

            # Deduplicate
            key = quote_text[:80]
            if key in seen:
                continue
            seen.add(key)

            # Extract categories from text after the blockquote
            after_clean = re.sub(r'<[^>]+>', ' ', after_raw)
            after_clean = self._decode(after_clean)
            categories = self._extract_categories(after_clean)

            if not categories:
                categories = ["general"]

            # One pair per category
            for category in categories:
                pairs.append({
                    "instruction": "You are Steve Jobs. Respond as Steve Jobs.",
                    "input": f"Tell me about {category.lower()}.",
                    "output": quote_text,
                    "category": category,
                    "source": QUOTES_URL
                })

        return pairs

    def _extract_categories(self, text: str) -> List[str]:
        found = []
        for category in KNOWN_CATEGORIES:
            if re.search(r'\b' + re.escape(category) + r'\b', text, re.IGNORECASE):
                found.append(category)
        return found

    def _decode(self, text: str) -> str:
        return (text
            .replace('&amp;', '&')
            .replace('&lt;', '<')
            .replace('&gt;', '>')
            .replace('&nbsp;', ' ')
            .replace('&quot;', '"')
            .replace('&#39;', "'")
            .replace('&ldquo;', '\u201c')
            .replace('&rdquo;', '\u201d')
            .replace('&lsquo;', '\u2018')
            .replace('&rsquo;', '\u2019')
            .replace('&mdash;', '\u2014')
            .replace('&ndash;', '\u2013')
        )

    def save(self, pairs: List[Dict], output_path: str):
        import os
        os.makedirs(
            os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
            exist_ok=True
        )
        with open(output_path, "w", encoding="utf-8") as f:
            for pair in pairs:
                f.write(json.dumps(pair, ensure_ascii=False) + "\n")
        print(f"💾 Saved to: {output_path}")

    def preview(self, pairs: List[Dict], n: int = 3):
        print(f"\n📋 Sample pairs:")
        for pair in pairs[:n]:
            print(f"\n  Category:    {pair['category']}")
            print(f"  Instruction: {pair['instruction']}")
            print(f"  Input:       {pair['input']}")
            print(f"  Output:      {pair['output'][:120]}...")


if __name__ == "__main__":
    scraper = QuotesScraper("Steve Jobs")
    pairs = scraper.scrape()

    if pairs:
        scraper.preview(pairs)
        scraper.save(pairs, "./data/training/steve_jobs/quotes_pairs.jsonl")

        print(f"\n📊 Pairs by category:")
        cats = Counter(p["category"] for p in pairs)
        for cat, count in cats.most_common():
            print(f"   {cat}: {count}")