"""
Chunk and Filter Tool
Path: src/function_schema/chunk_and_filter.py
"""

import re
import json
import hashlib
from typing import List, Tuple, Set

CHUNK_MIN_WORDS = 8
CHUNK_MAX_WORDS = 250

BOILERPLATE = [
    r"all rights reserved",
    r"privacy policy",
    r"terms of (use|service)",
    r"cookie policy",
    r"subscribe (now|today)",
    r"sign up for",
    r"advertisement",
    r"sponsored content",
    r"share this (article|page)",
    r"follow us on",
    r"click here to",
    r"read more",
]


class ChunkAndFilter:

    def __init__(self):
        self.name = "chunk_and_filter"
        self.description = (
            "Splits raw scraped text into clean segments. "
            "For quote pages: splits each quote as its own chunk. "
            "For interview/fallback: splits by paragraph (60-250 words). "
            "Removes boilerplate and deduplicates across the run. "
            "Call with text (str), seen_hashes (JSON str), and "
            "source_type (str: quote/interview/fallback). "
            "Returns JSON: {chunks: [...], seen_hashes: [...]}"
        )

    def execute(
        self,
        text: str,
        seen_hashes: str = "[]",
        source_type: str = "fallback"
    ) -> str:
        seen = set(json.loads(seen_hashes))
        chunks, updated_seen = self._process(text, seen, source_type)
        return json.dumps({"chunks": chunks, "seen_hashes": list(updated_seen)})

    def _process(
        self, text: str, seen: Set[str], source_type: str
    ) -> Tuple[List[str], Set[str]]:

        if source_type == "quote":
            raw_chunks = self._split_quotes(text)
        else:
            raw_chunks = self._split_paragraphs(text)

        clean        = []
        updated_seen = set(seen)

        for chunk in raw_chunks:
            chunk = chunk.strip()
            if not chunk:
                continue

            wc = len(chunk.split())
            if source_type == "quote":
                if wc < CHUNK_MIN_WORDS or wc > CHUNK_MAX_WORDS:
                    continue
            else:
                if wc < 60 or wc > CHUNK_MAX_WORDS:
                    continue

            h = hashlib.md5(chunk.lower().encode()).hexdigest()
            if h in updated_seen:
                continue
            updated_seen.add(h)

            if self._is_boilerplate(chunk):
                continue

            alpha = sum(1 for c in chunk if c.isalpha())
            if len(chunk) > 0 and alpha / len(chunk) < 0.55:
                continue

            clean.append(chunk)

        return clean, updated_seen

    def _split_quotes(self, text: str) -> List[str]:
        return [q.strip() for q in re.split(r"\n{2,}", text) if q.strip()]

    def _split_paragraphs(self, text: str) -> List[str]:
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        chunks, buffer = [], ""

        for para in paragraphs:
            combined = (buffer + " " + para).strip()
            wc = len(combined.split())

            if wc > CHUNK_MAX_WORDS:
                if buffer:
                    chunks.append(buffer.strip())
                if len(para.split()) > CHUNK_MAX_WORDS:
                    chunks.extend(self._split_sentences(para))
                else:
                    buffer = para
            else:
                buffer = combined

        if buffer and len(buffer.split()) >= 60:
            chunks.append(buffer.strip())

        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        sentences   = re.split(r"(?<=[.!?])\s+", text)
        chunks, buf = [], ""
        for s in sentences:
            candidate = (buf + " " + s).strip()
            if len(candidate.split()) >= 60:
                chunks.append(candidate)
                buf = ""
            else:
                buf = candidate
        if buf and len(buf.split()) >= 60:
            chunks.append(buf)
        return chunks

    def _is_boilerplate(self, text: str) -> bool:
        lower = text.lower()
        return any(re.search(p, lower) for p in BOILERPLATE)


if __name__ == "__main__":
    sample = """
    Design is not just what it looks like and feels like. Design is how it works.

    Innovation distinguishes between a leader and a follower.

    Your time is limited, so don't waste it living someone else's life.

    Subscribe now to get more quotes delivered to your inbox.
    """
    tool   = ChunkAndFilter()
    result = json.loads(tool.execute(text=sample, seen_hashes="[]", source_type="quote"))
    print(f"Chunks: {len(result['chunks'])}")
    for c in result["chunks"]:
        print(f"  [{len(c.split())} words] {c[:80]}")