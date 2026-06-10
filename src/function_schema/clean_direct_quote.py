"""
Clean Direct Quote Tool
Path: src/function_schema/clean_direct_quote.py
"""

import os
from function_schema.llm_config import get_client, get_model
import re
from typing import Optional


class CleanDirectQuote:

    def __init__(self):
        self.name = "clean_direct_quote"
        self.description = (
            "Cleans a raw first-person quote. Strips attribution, normalises "
            "formatting, removes partial sentences. Only calls LLM if quote "
            "is messy. Call with quote (str) and subject (str). "
            "Returns cleaned quote string."
        )
        self.model = get_model()
        self.client = None

    def _get_client(self):
        if self.client is None:
            self.client = get_client()
        return self.client

    def execute(self, quote: str, subject: str) -> str:
        cleaned = self._clean_deterministic(quote, subject)
        if not cleaned or len(cleaned.split()) < 8:
            return ""
        if self._needs_llm(cleaned):
            result = self._clean_with_llm(cleaned, subject)
            return result or cleaned
        return cleaned

    def _clean_deterministic(self, quote: str, subject: str) -> str:
        quote = re.sub(
            r"[—\-~]\s*" + re.escape(subject) + r".*$", "", quote,
            flags=re.IGNORECASE
        )
        quote = re.sub(r"[—\-~]\s*\w[\w\s,\.]+$", "", quote)
        quote = re.sub(r"\(.*?\d{4}.*?\)", "", quote)
        quote = re.sub(r"\[.*?\]", "", quote)
        quote = quote.strip('" \'"\'«»')
        quote = re.sub(r"\s+", " ", quote).strip()
        return quote

    def _needs_llm(self, quote: str) -> bool:
        if quote and quote[-1] not in ".!?\"'":
            return True
        if re.search(r"\[.*?\]", quote):
            return True
        if len(quote.split()) > 200:
            return True
        return False

    def _clean_with_llm(self, quote: str, subject: str) -> Optional[str]:
        prompt = (
            f"Subject: {subject}\n\n"
            f"Raw quote:\n{quote}\n\n"
            f"Clean this quote for use as a training response. "
            f"Keep first person. Remove incomplete trailing sentences. "
            f"Remove interviewer interjections in brackets. "
            f"Do not add or invent any content.\n\n"
            f"Return ONLY the cleaned quote. No preamble."
        )
        try:
            resp = self._get_client().chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
            )
            result = resp.choices[0].message.content.strip().strip('"\'')
            if len(result.split()) >= 8:
                return result
        except Exception as e:
            print(f"   CleanDirectQuote error: {e}")
        return None


if __name__ == "__main__":
    tool = CleanDirectQuote()
    samples = [
        '"Design is not just what it looks like. Design is how it works." — Steve Jobs, 2003',
        "Innovation distinguishes between a leader and a follower. [Applause] I've always believed that.",
        "Your time is limited, so don't waste it living someone else's life",
    ]
    for s in samples:
        result = tool.execute(quote=s, subject="Steve Jobs")
        print(f"IN  : {s[:80]}")
        print(f"OUT : {result}")
        print()