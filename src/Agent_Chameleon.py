"""
Agent Chameleon — Training Pair Generator
==========================================
Autonomous agent that scrapes the web for a given subject and
generates high-quality LLM fine-tuning pairs in your chosen format.

Usage:
    python src/Agent_Chameleon.py

Workflow:
    Phase 1 — direct sources (quotes + interviews)
    Phase 2 — fallback transform (only if pairs < target after Phase 1)
"""

import os
import re
import json
import time
from typing import List, Dict, Optional

from dotenv import load_dotenv
from openai import OpenAI

from function_schema.tool_registry import ToolRegistry

load_dotenv()

# ── LLM config ────────────────────────────────────────────────────────

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
API_BASE_URL = os.getenv("HF_API_BASE", "https://api.groq.com/openai/v1")
MODEL_NAME   = os.getenv("HF_MODEL",    "llama-3.3-70b-versatile")

QUALITY_THRESHOLD = 7
REQUEST_DELAY     = 1.0
MAX_RETRIES       = 2


class AgentChameleon:

    def __init__(self):
        self.client = OpenAI(api_key=GROQ_API_KEY, base_url=API_BASE_URL)

        self.tools = ToolRegistry()
        self.tools.auto_discover(
            os.path.join(os.path.dirname(__file__), "function_schema")
        )

        self.subject       : str            = ""
        self.target_pairs  : int            = 0
        self.output_format : str            = ""
        self.output_path   : str            = ""

        self.pairs_written : int            = 0
        self.seen_hashes   : list           = []
        self.topic_counts  : Dict[str, int] = {}
        self.session_log   : List[Dict]     = []

    def main(self):
        self._print_header()

        self.subject = input("  Subject (e.g. Steve Jobs): ").strip()
        if not self.subject:
            print("  Subject cannot be empty.")
            return

        target_raw = input("  Target pairs (default 1000): ").strip()
        self.target_pairs = int(target_raw) if target_raw.isdigit() else 1000

        fmt_raw = input(
            "  Format — alpaca / sharegpt / openai (default alpaca): "
        ).strip().lower()
        self.output_format = (
            fmt_raw if fmt_raw in ["alpaca", "sharegpt", "openai"] else "alpaca"
        )

        safe_name        = re.sub(r"[^a-z0-9_]", "_", self.subject.lower())
        self.output_path = f"./data/output/{safe_name}.jsonl"

        print(f"\n  Config:")
        print(f"     Subject  : {self.subject}")
        print(f"     Pairs    : {self.target_pairs}")
        print(f"     Format   : {self.output_format}")
        print(f"     Output   : {self.output_path}\n")

        self._run()

    def _run(self):
        # URL limit scales with target — 3x headroom per topic
        url_limit = max(self.target_pairs * 3, 90)

        print("  Discovering sources...")
        print(f"  DEBUG tools registered: {self.tools.list_tools()}")
        raw = self.tools.execute("discover_urls", {
             "subject":      self.subject,
             "limit":        url_limit,
             "target_pairs": self.target_pairs
             })
        print(f"  DEBUG raw result: {raw[:200] if raw else 'EMPTY'}")

        try:
            all_sources = json.loads(raw) if raw else []
        except Exception:
            all_sources = []

        if not all_sources:
            print("  No URLs found. Check your subject and network connection.")
            return

        quotes     = [s for s in all_sources if s["source_type"] == "quote"]
        interviews = [s for s in all_sources if s["source_type"] == "interview"]
        fallback   = [s for s in all_sources if s["source_type"] == "fallback"]

        print(f"\n  quotes: {len(quotes)}  "
              f"interviews: {len(interviews)}  "
              f"fallback: {len(fallback)}\n")

        # Phase 1 — direct sources
        print("  Phase 1 — quotes + interviews")
        self._process_sources(quotes,     "quote")
        self._process_sources(interviews, "interview")

        # Phase 2 — fallback only if still short
        if self.pairs_written < self.target_pairs:
            remaining = self.target_pairs - self.pairs_written
            print(f"\n  Phase 2 — fallback "
                  f"({self.pairs_written}/{self.target_pairs}, "
                  f"need {remaining} more)")
            self._process_sources(fallback, "fallback")

        self._print_summary()

    def _process_sources(self, sources: List[Dict], source_type: str):
        for i, source in enumerate(sources):
            if self.pairs_written >= self.target_pairs:
                break
            url   = source["url"]
            topic = source.get("topic", "general")
            print(f"  [{i+1}/{len(sources)}] [{source_type:10}] "
                  f"[{topic[:18]:18}] {url[:50]}")

            if source_type == "quote":
                self._process_quote(url, topic)
            elif source_type == "interview":
                self._process_interview(url, topic)
            else:
                self._process_fallback(url, topic)

            time.sleep(REQUEST_DELAY)

    def _process_quote(self, url: str, topic: str):
        scraped = json.loads(
            self.tools.execute("scrape_url", {
                "url": url, "source_type": "quote"
            })
        )
        text = scraped.get("text", "")
        if not text:
            self._log(url, "quote", "skip", "empty")
            return

        result = json.loads(
            self.tools.execute("chunk_and_filter", {
                "text":        text,
                "seen_hashes": json.dumps(self.seen_hashes),
                "source_type": "quote"
            })
        )
        chunks           = result.get("chunks", [])
        self.seen_hashes = result.get("seen_hashes", self.seen_hashes)

        print(f"     {len(chunks)} quotes")

        for chunk in chunks:
            if self.pairs_written >= self.target_pairs:
                break
            cleaned = self.tools.execute("clean_direct_quote", {
                "quote": chunk, "subject": self.subject
            })
            if not cleaned or len(cleaned.split()) < 8:
                continue
            question = self.tools.execute("generate_question", {
                "response": cleaned, "subject": self.subject
            })
            if not question:
                continue
            self._score_and_write(question, cleaned, topic, url)

    def _process_interview(self, url: str, topic: str):
        scraped = json.loads(
            self.tools.execute("scrape_url", {
                "url": url, "source_type": "interview"
            })
        )
        text = scraped.get("text", "")
        if not text or len(text.split()) < 100:
            self._log(url, "interview", "skip", "too short")
            return

        pairs_raw = self.tools.execute("fix_interview_pairs", {
            "transcript": text, "subject": self.subject
        })
        try:
            pairs = json.loads(pairs_raw)
        except Exception:
            self._log(url, "interview", "skip", "could not parse pairs")
            return

        print(f"     {len(pairs)} interview pairs")

        for pair in pairs:
            if self.pairs_written >= self.target_pairs:
                break
            question = pair.get("question", "").strip()
            response = pair.get("response", "").strip()
            if not question or not response:
                continue
            self._score_and_write(question, response, topic, url)

    def _process_fallback(self, url: str, topic: str):
        scraped = json.loads(
            self.tools.execute("scrape_url", {
                "url": url, "source_type": "fallback"
            })
        )
        text = scraped.get("text", "")
        if not text or len(text.split()) < 100:
            self._log(url, "fallback", "skip", "too short")
            return

        result = json.loads(
            self.tools.execute("chunk_and_filter", {
                "text":        text,
                "seen_hashes": json.dumps(self.seen_hashes),
                "source_type": "fallback"
            })
        )
        chunks           = result.get("chunks", [])
        self.seen_hashes = result.get("seen_hashes", self.seen_hashes)

        print(f"     {len(chunks)} chunks")

        for chunk in chunks:
            if self.pairs_written >= self.target_pairs:
                break
            self._process_fallback_chunk(chunk, topic, url)

    def _process_fallback_chunk(
        self, chunk: str, topic: str, source_url: str, retry: int = 0
    ):
        response = self.tools.execute("transform_to_voice", {
            "chunk": chunk, "subject": self.subject
        })
        if not response or len(response.split()) < 15:
            return

        question = self.tools.execute("generate_question", {
            "response": response, "subject": self.subject
        })
        if not question:
            return

        scored = self._score_and_write(question, response, topic, source_url)
        if not scored and retry < MAX_RETRIES:
            self._process_fallback_chunk(
                chunk, topic, source_url, retry=retry + 1
            )

    def _score_and_write(
        self,
        question: str,
        response: str,
        topic: str,
        source_url: str
    ) -> bool:
        score = int(
            self.tools.execute("score_pair", {
                "question": question,
                "response": response,
                "subject":  self.subject
            }) or 0
        )

        if score < QUALITY_THRESHOLD:
            self._log(source_url, "score", "low", f"score {score}")
            return False

        self.tools.execute("write_output", {
            "question":      question,
            "response":      response,
            "subject":       self.subject,
            "output_format": self.output_format,
            "output_path":   self.output_path,
            "pair_index":    self.pairs_written,
        })

        self.pairs_written += 1
        self.topic_counts[topic] = self.topic_counts.get(topic, 0) + 1
        self._log(source_url, "write", "ok",
                  f"pair {self.pairs_written} score={score}")

        if self.pairs_written % 50 == 0:
            print(f"\n  {self.pairs_written}/{self.target_pairs} pairs written")
            self._print_topic_balance()

        return True

    def _log(self, source: str, stage: str, status: str, note: str):
        self.session_log.append({
            "source": source[:60], "stage": stage,
            "status": status, "note": note
        })

    def _print_header(self):
        print("\n" + "=" * 60)
        print("  Agent Chameleon — Training Pair Generator")
        print("=" * 60 + "\n")

    def _print_topic_balance(self):
        if not self.topic_counts:
            return
        print("  Topic balance:")
        for topic, count in sorted(
            self.topic_counts.items(), key=lambda x: -x[1]
        ):
            bar = "█" * min(count, 30)
            print(f"    {topic[:22]:22} {bar} {count}")

    def _print_summary(self):
        ok      = len([l for l in self.session_log if l["status"] == "ok"])
        skipped = len([l for l in self.session_log
                       if l["status"] in ("skip", "low")])
        print("\n" + "=" * 60)
        print(f"  Done.")
        print(f"  Pairs written : {self.pairs_written}")
        print(f"  Logged ok     : {ok}")
        print(f"  Skipped/low   : {skipped}")
        print(f"  Output        : {self.output_path}")
        print()
        self._print_topic_balance()
        print("=" * 60 + "\n")


if __name__ == "__main__":
    agent = AgentChameleon()
    agent.main()