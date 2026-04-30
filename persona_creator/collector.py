"""
Data Collection Pipeline
Path: src/Agent/persona/collector.py

Collects verified, multi-source data for any named persona.
Improvements over v1:
  - More Wikipedia sections collected
  - Better quote extraction and deduplication
  - More varied Q&A pair generation (not just "Tell me about X")
  - Conversational Q&A pairs generated from biographical content
  - Archive.org inlined — no separate import needed
"""

import os
import re
import json
import time
import requests
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class PersonaDocument:
    source: str
    source_url: str
    title: str
    content: str
    doc_type: str
    persona: str
    collected_at: str = field(default_factory=lambda: datetime.now().isoformat())
    word_count: int = 0

    def __post_init__(self):
        self.word_count = len(self.content.split())


class PersonaDataCollector:

    def __init__(self, persona_name: str, verbose: bool = True):
        self.persona_name = persona_name
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"PersonaResearchBot/1.0 (educational; {persona_name})"
        })

    def collect(self) -> List[PersonaDocument]:
        documents = []
        self._log(f"\n📚 Starting data collection for: {self.persona_name}")
        self._log("=" * 55)

        collectors = [
            ("Wikipedia",   self._collect_wikipedia),
            ("Wikiquote",   self._collect_wikiquote),
            ("Archive.org", self._collect_archive),
        ]

        for name, fn in collectors:
            self._log(f"\n🔍 Collecting from {name}...")
            try:
                docs = fn()
                documents.extend(docs)
                self._log(f"   ✅ {len(docs)} documents collected")
            except Exception as e:
                self._log(f"   ⚠️  {name} failed: {e}")

        total_words = sum(d.word_count for d in documents)
        self._log(f"\n📊 Total: {len(documents)} documents, {total_words:,} words")
        return documents

    # ── Wikipedia ─────────────────────────────────────────────────────

    def _collect_wikipedia(self) -> List[PersonaDocument]:
        docs = []

        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": self.persona_name,
            "format": "json",
            "srlimit": 3
        }
        resp = self.session.get("https://en.wikipedia.org/w/api.php", params=search_params, timeout=15)
        results = resp.json().get("query", {}).get("search", [])
        if not results:
            return docs

        page_title = results[0]["title"]

        # Full article summary
        summary_resp = self.session.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{page_title.replace(' ', '_')}",
            timeout=15
        )
        if summary_resp.status_code == 200:
            data = summary_resp.json()
            content = data.get("extract", "")
            if content:
                docs.append(PersonaDocument(
                    source="wikipedia",
                    source_url=data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                    title=f"Wikipedia: {data.get('title', page_title)}",
                    content=content,
                    doc_type="biography",
                    persona=self.persona_name
                ))

        # All sections — expanded keyword list to capture more
        sections_resp = self.session.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "parse",
                "page": page_title,
                "prop": "sections|wikitext",
                "format": "json"
            },
            timeout=15
        )

        if sections_resp.status_code == 200:
            sections = sections_resp.json().get("parse", {}).get("sections", [])

            # Broader keyword list — captures more sections
            useful_keywords = [
                "early", "life", "career", "personal", "philosophy", "legacy",
                "death", "education", "founding", "return", "pixar", "apple",
                "design", "leadership", "style", "beliefs", "later", "business",
                "product", "innovation", "management", "health", "family",
                "childhood", "youth", "work", "company", "vision", "impact",
                "achievements", "awards", "criticism", "controversy", "character"
            ]

            for section in sections[:25]:  # Increased from 15 to 25
                title = section.get("line", "").lower()
                if any(kw in title for kw in useful_keywords):
                    content = self._fetch_wikipedia_section(page_title, section.get("index", "0"))
                    if content and len(content) > 80:  # Lowered threshold from 100
                        docs.append(PersonaDocument(
                            source="wikipedia",
                            source_url=f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}",
                            title=f"Wikipedia — {section.get('line', '')}",
                            content=content,
                            doc_type="biography",
                            persona=self.persona_name
                        ))
                    time.sleep(0.3)

        return docs

    def _fetch_wikipedia_section(self, page_title: str, section_index: str) -> str:
        try:
            resp = self.session.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "parse",
                    "page": page_title,
                    "prop": "wikitext",
                    "section": section_index,
                    "format": "json"
                },
                timeout=10
            )
            wikitext = resp.json().get("parse", {}).get("wikitext", {}).get("*", "")
            return self._clean_wikitext(wikitext)
        except Exception:
            return ""

    def _clean_wikitext(self, text: str) -> str:
        text = re.sub(r'\{\{[^}]*\}\}', '', text)
        text = re.sub(r'\[\[File:[^\]]*\]\]', '', text)
        text = re.sub(r'\[\[Image:[^\]]*\]\]', '', text)
        text = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', text)
        text = re.sub(r'\[https?://\S+\s([^\]]+)\]', r'\1', text)
        text = re.sub(r"'{2,3}", '', text)
        text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    # ── Wikiquote ─────────────────────────────────────────────────────

    def _collect_wikiquote(self) -> List[PersonaDocument]:
        docs = []

        resp = self.session.get(
            "https://en.wikiquote.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": self.persona_name,
                "format": "json",
                "srlimit": 3
            },
            timeout=15
        )
        results = resp.json().get("query", {}).get("search", [])
        if not results:
            return docs

        page_title = results[0]["title"]

        content_resp = self.session.get(
            "https://en.wikiquote.org/w/api.php",
            params={
                "action": "parse",
                "page": page_title,
                "prop": "wikitext",
                "format": "json"
            },
            timeout=15
        )
        if content_resp.status_code != 200:
            return docs

        wikitext = content_resp.json().get("parse", {}).get("wikitext", {}).get("*", "")
        quotes = self._extract_quotes(wikitext)

        if quotes:
            # Store all quotes as one document
            quote_text = "\n\n".join([f'"{q}"' for q in quotes])
            docs.append(PersonaDocument(
                source="wikiquote",
                source_url=f"https://en.wikiquote.org/wiki/{page_title.replace(' ', '_')}",
                title=f"Wikiquote: {page_title}",
                content=quote_text,
                doc_type="quote",
                persona=self.persona_name
            ))
            self._log(f"   📝 {len(quotes)} quotes extracted")

        return docs

    def _extract_quotes(self, wikitext: str) -> List[str]:
        quotes = []
        seen = set()
        lines = wikitext.split('\n')

        for line in lines:
            if line.startswith('*') and not line.startswith('**'):
                clean = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', line)
                clean = re.sub(r'\{\{[^}]*\}\}', '', clean)
                clean = re.sub(r"'{2,3}", '', clean)
                clean = re.sub(r'<[^>]+>', '', clean)
                clean = clean.lstrip('*').strip()

                # Deduplicate and filter
                if 20 < len(clean) < 1000 and clean not in seen:
                    seen.add(clean)
                    quotes.append(clean)

        return quotes

    # ── Archive.org ───────────────────────────────────────────────────

    def _collect_archive(self) -> List[PersonaDocument]:
        """Direct URL fetching from known sources — no search needed."""

        KNOWN_SOURCES = {
            "Steve Jobs": [
                {
                    "url": "https://web.archive.org/web/20240101/https://news.stanford.edu/2005/06/14/jobs-061505/",
                    "title": "Stanford Commencement Address 2005",
                    "doc_type": "speech"
                },
                {
                    "url": "https://web.archive.org/web/20240101/https://www.apple.com/stevejobs/",
                    "title": "Apple Tribute to Steve Jobs",
                    "doc_type": "biography"
                },
            ]
        }

        docs = []
        sources = KNOWN_SOURCES.get(self.persona_name, [])

        if not sources:
            self._log(f"   ⚠️  No known archive sources for {self.persona_name}")
            return docs

        for source in sources:
            self._log(f"   Fetching: {source['title']}...")
            try:
                resp = self.session.get(source["url"], timeout=15)
                if resp.status_code != 200:
                    self._log(f"   ⚠️  HTTP {resp.status_code} — skipping")
                    continue

                text = re.sub(r'<script[^>]*>.*?</script>', '', resp.text, flags=re.DOTALL)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
                text = re.sub(r'<[^>]+>', ' ', text)
                text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                text = text.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&#39;', "'")
                text = re.sub(r'[ \t]+', ' ', text)
                text = re.sub(r'\n{3,}', '\n\n', text).strip()

                if len(text) < 200:
                    self._log(f"   ⚠️  Too little content — skipping")
                    continue

                docs.append(PersonaDocument(
                    source="archive_org",
                    source_url=source["url"],
                    title=source["title"],
                    content=text[:8000],  # Cap at 8000 chars
                    doc_type=source["doc_type"],
                    persona=self.persona_name
                ))
                self._log(f"   ✅ {len(text.split())} words extracted")
                time.sleep(1)

            except Exception as e:
                self._log(f"   ⚠️  Failed: {e}")

        return docs

    # ── Save output ───────────────────────────────────────────────────

    def save(self, documents: List[PersonaDocument], output_dir: str) -> Dict:
        os.makedirs(output_dir, exist_ok=True)

        # Raw documents
        raw_path = os.path.join(output_dir, "raw_documents.json")
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump([asdict(d) for d in documents], f, indent=2)
        self._log(f"\n💾 Raw documents: {raw_path}")

        # Fine-tune JSONL
        qa_pairs = self._generate_qa_pairs(documents)
        finetune_path = os.path.join(output_dir, "finetune.jsonl")
        with open(finetune_path, "w", encoding="utf-8") as f:
            for pair in qa_pairs:
                f.write(json.dumps(pair) + "\n")
        self._log(f"💾 Fine-tune pairs: {finetune_path} ({len(qa_pairs)} pairs)")

        return {
            "raw": raw_path,
            "finetune": finetune_path,
            "stats": {
                "documents": len(documents),
                "qa_pairs": len(qa_pairs),
                "total_words": sum(d.word_count for d in documents)
            }
        }

    def _generate_qa_pairs(self, documents: List[PersonaDocument]) -> List[Dict]:
        """
        Generate varied Q&A pairs from collected documents.
        Uses multiple question templates per content piece
        to create more diverse training data.
        """
        pairs = []
        persona = self.persona_name
        seen_outputs = set()

        # Question templates for biographical content
        bio_templates = [
            ("You are {persona}. Respond in character based on your real experiences.",
             "Tell me about yourself."),
            ("You are {persona}. Answer as yourself using your actual history and beliefs.",
             "What shaped who you are?"),
            ("You are {persona}. Share your perspective on this topic.",
             "What do you believe in?"),
            ("You are {persona}. Reflect on your life and work.",
             "What are you most proud of?"),
            ("You are {persona}. Speak in your own voice.",
             "How do you see the world?"),
            ("You are {persona}. Respond authentically.",
             "What drives you?"),
            ("You are {persona}. Respond as yourself.",
             "What have you learned from your experiences?"),
        ]

        # Question templates for quotes
        quote_templates = [
            ("You are {persona}. Share your thoughts authentically.",
             ""),
            ("You are {persona}. Express your beliefs in your own words.",
             "What do you think about life and work?"),
            ("You are {persona}. Speak from the heart.",
             "Share something important with me."),
            ("You are {persona}. Give me your honest perspective.",
             "What wisdom would you share?"),
        ]

        for doc in documents:
            if doc.doc_type == "quote":
                quotes = [q.strip('"').strip() for q in doc.content.split('\n\n') if q.strip()]
                for quote in quotes:
                    if len(quote) < 30:
                        continue
                    # Deduplicate
                    key = quote[:80]
                    if key in seen_outputs:
                        continue
                    seen_outputs.add(key)

                    # Use multiple templates per quote
                    for instruction_template, user_input in quote_templates:
                        instruction = instruction_template.format(persona=persona)
                        pairs.append({
                            "instruction": instruction,
                            "input": user_input,
                            "output": quote,
                            "source": doc.source_url
                        })

            elif doc.doc_type in ["biography", "speech", "interview"]:
                paragraphs = [p.strip() for p in doc.content.split('\n\n') if len(p.strip()) > 80]

                for para in paragraphs[:15]:  # Increased from 10
                    key = para[:80]
                    if key in seen_outputs:
                        continue
                    seen_outputs.add(key)

                    # Use multiple templates per paragraph
                    for instruction_template, user_input in bio_templates[:3]:
                        instruction = instruction_template.format(persona=persona)
                        pairs.append({
                            "instruction": instruction,
                            "input": user_input,
                            "output": para,
                            "source": doc.source_url
                        })

                    # Also add a source-specific pair
                    pairs.append({
                        "instruction": f"You are {persona}. Based on your life and experiences, respond naturally.",
                        "input": f"Tell me about: {doc.title}",
                        "output": para,
                        "source": doc.source_url
                    })

        self._log(f"   Generated {len(pairs)} Q&A pairs from {len(documents)} documents")
        return pairs

    def _log(self, message: str):
        if self.verbose:
            print(message)


# ── Entry point ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    name = sys.argv[1] if len(sys.argv) > 1 else "Steve Jobs"
    output_dir = f"./data/training/{name.lower().replace(' ', '_')}"

    collector = PersonaDataCollector(name)
    documents = collector.collect()
    stats = collector.save(documents, output_dir)

    print(f"\n{'='*55}")
    print(f"Collection complete for: {name}")
    print(f"  Documents:  {stats['stats']['documents']}")
    print(f"  QA pairs:   {stats['stats']['qa_pairs']}")
    print(f"  Words:      {stats['stats']['total_words']:,}")
    print(f"  Output dir: {output_dir}")