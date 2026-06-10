"""
Agent Chameleon — Training Pair Generator
======================================
Autonomous agent that scrapes the web for a given subject and
generates high-quality LLM fine-tuning pairs in your chosen format.

Usage:
    python Agent_Chameleon.py

The agent will ask for:
    - Subject        (e.g. "Marie Curie", "CQC safe staffing")
    - Target pairs   (e.g. 1000)
    - Output format  (alpaca / sharegpt / openai)

Workflow:
    collect  →  transform  →  output
    LLM reads the result of each stage and decides whether to
    continue, retry with a different source, or stop early.
"""

import os
import re
import json
import time
from datetime import datetime
from typing import List, Dict, Optional

from dotenv import load_dotenv
from openai import OpenAI

from function_schema.tool_registry import ToolRegistry

load_dotenv()

# ── LLM config ────────────────────────────────────────────────────────

HF_TOKEN     = os.getenv("HF_TOKEN")
API_BASE_URL = os.getenv("HF_API_BASE", "https://router.huggingface.co/v1")
MODEL_NAME   = os.getenv("HF_MODEL",    "meta-llama/Llama-3.3-70B-Instruct")

QUALITY_THRESHOLD = 7
REQUEST_DELAY     = 1.0


# ══════════════════════════════════════════════════════════════════════
# AGENT
# ══════════════════════════════════════════════════════════════════════

class AgentChameleon:
    """
    Autonomous training pair generator.
    Workflow stages are defined here. Tools live in function_schema/.
    The LLM makes quality decisions between stages.
    """

    def __init__(self):
        # ── LLM client ────────────────────────────────────────────────
        self.client = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL)

        # ── Tool registry (auto-discovers function_schema/) ───────────
        self.tools = ToolRegistry()
        self.tools.auto_discover(
            os.path.join(os.path.dirname(__file__), "function_schema")
        )

        # ── Session config (set by main()) ────────────────────────────
        self.subject       : str = ""
        self.target_pairs  : int = 0
        self.output_format : str = ""
        self.output_path   : str = ""

        # ── Runtime state ─────────────────────────────────────────────
        self.pairs_written : int  = 0
        self.seen_hashes   : list = []
        self.session_log   : List[Dict] = []

    # ══════════════════════════════════════════════════════════════════
    # ENTRY POINT
    # ══════════════════════════════════════════════════════════════════

    def main(self):
        self._print_header()

        # ── User inputs ───────────────────────────────────────────────
        self.subject = input("  Subject (e.g. Marie Curie): ").strip()
        if not self.subject:
            print("  Subject cannot be empty.")
            return

        target_raw = input("  Target pairs (default 1000): ").strip()
        self.target_pairs = int(target_raw) if target_raw.isdigit() else 1000

        fmt_raw = input("  Format — alpaca / sharegpt / openai (default alpaca): ").strip().lower()
        self.output_format = fmt_raw if fmt_raw in ["alpaca", "sharegpt", "openai"] else "alpaca"

        timestamp        = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name        = re.sub(r"[^a-z0-9_]", "_", self.subject.lower())
        self.output_path = f"./data/output/{safe_name}_{timestamp}.jsonl"

        print(f"\n  ✅ Config saved:")
        print(f"     Subject  : {self.subject}")
        print(f"     Pairs    : {self.target_pairs}")
        print(f"     Format   : {self.output_format}")
        print(f"     Output   : {self.output_path}")
        print(f"\n  Starting...\n")

        # ── Run workflow ──────────────────────────────────────────────
        self._run()

    # ══════════════════════════════════════════════════════════════════
    # WORKFLOW
    # ══════════════════════════════════════════════════════════════════

    def _run(self):
        """
        Main loop. Discovers URL batches, then processes each source
        through collect → transform → output. LLM checks quality
        after transform and decides whether to write or retry.
        """
        url_limit = max(self.target_pairs * 3, 60)
        urls      = self._stage_collect_urls(url_limit)

        if not urls:
            print("  ❌ No URLs found. Check your subject and network connection.")
            return

        print(f"  Found {len(urls)} candidate sources\n")

        for i, url in enumerate(urls):
            if self.pairs_written >= self.target_pairs:
                break

            print(f"  [{i+1}/{len(urls)}] {url[:70]}")
            self._process_source(url)
            time.sleep(REQUEST_DELAY)

        self._print_summary()

    def _stage_collect_urls(self, limit: int) -> List[str]:
        """Stage 1 — discover sources."""
        print("  Stage 1 — discovering sources...")
        raw = self.tools.execute("discover_urls", {
            "subject": self.subject,
            "limit": limit
        })
        try:
            return json.loads(raw)
        except Exception:
            return []

    def _process_source(self, url: str):
        """Scrape one URL, chunk it, then run each chunk through transform → score → write."""

        # ── Collect stage ─────────────────────────────────────────────
        text = self.tools.execute("scrape_url", {"url": url})
        if not text or len(text.split()) < 100:
            self._log(url, "collect", "skip", "too short or empty")
            return

        result = json.loads(
            self.tools.execute("chunk_and_filter", {
                "text": text,
                "seen_hashes": json.dumps(self.seen_hashes)
            })
        )
        chunks           = result.get("chunks", [])
        self.seen_hashes = result.get("seen_hashes", self.seen_hashes)

        if not chunks:
            self._log(url, "collect", "skip", "no valid chunks after filter")
            return

        print(f"     {len(chunks)} chunks")

        # ── Transform + output per chunk ──────────────────────────────
        for chunk in chunks:
            if self.pairs_written >= self.target_pairs:
                break
            self._stage_transform_and_output(chunk, url)

    def _stage_transform_and_output(self, chunk: str, source_url: str, retry: int = 0):
        """
        Stage 2 — transform chunk to voice and generate question.
        Stage 3 — LLM scores the pair; writes if above threshold, retries once if not.
        """
        max_retries = 2

        # Transform
        response = self.tools.execute("transform_to_voice", {
            "chunk": chunk,
            "subject": self.subject
        })
        if not response or len(response.split()) < 15:
            self._log(source_url, "transform", "skip", "empty response from LLM")
            return

        # Generate question
        question = self.tools.execute("generate_question", {
            "response": response,
            "subject": self.subject
        })
        if not question:
            self._log(source_url, "generate_question", "skip", "no question generated")
            return

        # Score — this is the LLM quality gate
        score = int(self.tools.execute("score_pair", {
            "question": question,
            "response": response,
            "subject": self.subject
        }) or 0)

        if score < QUALITY_THRESHOLD:
            self._log(source_url, "score", "low", f"score {score} < {QUALITY_THRESHOLD}")
            # Retry once with the same chunk — different temperature may improve output
            if retry < max_retries:
                print(f"     ↻ Score {score} — retrying transform ({retry+1}/{max_retries})")
                self._stage_transform_and_output(chunk, source_url, retry=retry + 1)
            return

        # Write
        write_result = self.tools.execute("write_output", {
            "question": question,
            "response": response,
            "subject": self.subject,
            "output_format": self.output_format,
            "output_path": self.output_path,
            "pair_index": self.pairs_written
        })

        self.pairs_written += 1
        self._log(source_url, "write", "ok", f"pair {self.pairs_written} score={score}")

        if self.pairs_written % 50 == 0:
            print(f"  ✅ {self.pairs_written}/{self.target_pairs} pairs written")

    # ══════════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════════

    def _log(self, source: str, stage: str, status: str, note: str):
        self.session_log.append({
            "source": source[:60],
            "stage": stage,
            "status": status,
            "note": note
        })

    def _print_header(self):
        print("\n" + "=" * 60)
        print("  Agent Chameleon — Training Pair Generator")
        print("=" * 60 + "\n")

    def _print_summary(self):
        ok      = len([l for l in self.session_log if l["status"] == "ok"])
        skipped = len([l for l in self.session_log if l["status"] in ("skip", "low")])
        print("\n" + "=" * 60)
        print(f"  Done.")
        print(f"  Pairs written : {self.pairs_written}")
        print(f"  Written       : {ok}")
        print(f"  Skipped/low   : {skipped}")
        print(f"  Output file   : {self.output_path}")
        print("=" * 60 + "\n")


# ══════════════════════════════════════════════════════════════════════
# RUN
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    agent = AgentChameleon()
    agent.main()