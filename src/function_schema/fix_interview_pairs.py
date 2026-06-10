"""
Fix Interview Pairs Tool
Path: function_schema/fix_interview_pairs.py

Takes a raw interview transcript and uses the LLM to correctly
match each question to its actual answer. Handles misaligned Q&A,
interviewer interjections, multi-part answers, and topic drift.

Returns a list of clean {question, response} pairs.

Standalone test:
    python function_schema/fix_interview_pairs.py
"""

import os
from function_schema.llm_config import get_client, get_model
import re
import json
from typing import List, Dict, Optional

# Minimum words for a response to be worth keeping
MIN_RESPONSE_WORDS = 20


class FixInterviewPairs:

    def __init__(self):
        self.name = "fix_interview_pairs"
        self.description = (
            "Takes a raw interview transcript and returns correctly matched "
            "question/answer pairs. The LLM identifies speaker turns, matches "
            "questions to their actual answers, and discards misaligned pairs. "
            "Call with transcript (str) and subject (str). "
            "Returns JSON list of {question, response} dicts."
        )
        self.model = get_model()
        self.client = None

    def _get_client(self):
        if self.client is None:
            self.client = get_client()
        return self.client

    def execute(self, transcript: str, subject: str) -> str:
        # Step 1: try deterministic Q/A extraction first
        pairs = self._extract_deterministic(transcript, subject)

        # Step 2: if deterministic fails or finds < 2 pairs, use LLM
        if len(pairs) < 2:
            pairs = self._extract_with_llm(transcript, subject)

        # Step 3: filter out weak pairs
        pairs = [
            p for p in pairs
            if p.get("question") and p.get("response")
            and len(p["response"].split()) >= MIN_RESPONSE_WORDS
        ]

        return json.dumps(pairs)

    def _extract_deterministic(self, transcript: str, subject: str) -> List[Dict]:
        """
        Look for explicit Q: / A: patterns or interviewer/subject name labels.
        Works when the transcript is already well-structured.
        """
        pairs = []

        # Pattern 1: Q: ... A: ...
        qa_pattern = re.findall(
            r"Q[:\.](.+?)A[:\.](.+?)(?=Q[:\.]|$)",
            transcript,
            re.DOTALL | re.IGNORECASE
        )
        if qa_pattern:
            for q, a in qa_pattern:
                pairs.append({
                    "question": q.strip(),
                    "response": a.strip()
                })
            return pairs

        # Pattern 2: Interviewer: ... Jobs: ... (or subject name)
        first_name = subject.split()[0]
        last_name  = subject.split()[-1]
        speaker_pattern = re.findall(
            r"(?:Interviewer|Reporter|Host)[:\s]+(.+?)"
            rf"(?:{first_name}|{last_name})[:\s]+(.+?)"
            r"(?=(?:Interviewer|Reporter|Host)[:\s]|$)",
            transcript,
            re.DOTALL | re.IGNORECASE
        )
        if speaker_pattern:
            for q, a in speaker_pattern:
                pairs.append({
                    "question": q.strip(),
                    "response": a.strip()
                })

        return pairs

    def _extract_with_llm(self, transcript: str, subject: str) -> List[Dict]:
        """
        Use LLM to identify and correctly match Q&A pairs from messy transcripts.
        Chunked to avoid context window issues with long transcripts.
        """
        # Chunk transcript into ~1500 word segments with overlap
        chunks = self._chunk_transcript(transcript, chunk_size=1500, overlap=200)
        all_pairs = []

        for chunk in chunks:
            pairs = self._llm_extract_chunk(chunk, subject)
            all_pairs.extend(pairs)

        # Deduplicate by response
        seen = set()
        unique = []
        for p in all_pairs:
            key = p.get("response", "")[:100]
            if key not in seen:
                seen.add(key)
                unique.append(p)

        return unique

    def _llm_extract_chunk(self, chunk: str, subject: str) -> List[Dict]:
        prompt = (
            f"Subject: {subject}\n\n"
            f"Interview transcript excerpt:\n{chunk}\n\n"
            f"Task: Extract all question/answer pairs from this transcript where "
            f"{subject} is the one answering.\n\n"
            f"Rules:\n"
            f"- Match each question to the answer {subject} actually gave\n"
            f"- If a question spans multiple turns, combine into one question\n"
            f"- If {subject}'s answer spans multiple turns, combine into one response\n"
            f"- Remove interviewer interjections from within answers\n"
            f"- Skip exchanges where {subject} gives a one-word answer\n"
            f"- The response must be in first person as {subject} speaking\n\n"
            f"Return ONLY a valid JSON array. Each item must have exactly two keys: "
            f"\"question\" and \"response\". No explanation, no markdown fences.\n"
            f"Example: "
            f'[{{"question": "What drives you?", "response": "I want to make a dent in the universe."}}]'
        )
        try:
            resp = self._get_client().chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1500,
            )
            raw = resp.choices[0].message.content.strip()
            raw = re.sub(r"```json|```", "", raw).strip()
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except Exception as e:
            print(f"   ⚠️  FixInterviewPairs LLM error: {e}")
        return []

    def _chunk_transcript(
        self, text: str, chunk_size: int = 1500, overlap: int = 200
    ) -> List[str]:
        words  = text.split()
        chunks = []
        start  = 0
        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunks.append(" ".join(words[start:end]))
            start += chunk_size - overlap
        return chunks


if __name__ == "__main__":
    sample_transcript = """
    Interviewer: Steve, what's your philosophy on design?

    Steve Jobs: Design is a funny word. Some people think design means how it looks.
    But of course, if you dig deeper, it's really how it works. The design of the Mac
    wasn't what it looked like, although that was part of it. Primarily, it was how
    it worked.

    Interviewer: And how did that philosophy develop for you personally?

    Steve Jobs: You know, I grew up with a father who was a craftsman. He believed
    that even the parts you couldn't see — the back of a cabinet, the inside of a
    fence — those had to be done beautifully. That stayed with me. It became part
    of how I think about every product we make.

    Interviewer: Some people say you're too much of a perfectionist.

    Steve Jobs: [laughs] I've heard that. But I think the people who say that have
    never shipped something they were truly proud of. Perfectionism isn't a flaw —
    it's the only standard worth having.
    """

    tool   = FixInterviewPairs()
    result = json.loads(tool.execute(transcript=sample_transcript, subject="Steve Jobs"))
    print(f"Extracted {len(result)} pairs:\n")
    for i, pair in enumerate(result, 1):
        print(f"Pair {i}:")
        print(f"  Q: {pair['question'][:100]}")
        print(f"  A: {pair['response'][:100]}")
        print()