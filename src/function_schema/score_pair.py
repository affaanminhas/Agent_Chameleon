"""
Score Pair Tool
Path: function_schema/score_pair.py

Scores a question/response training pair 1–10 on relevance,
quality, and training value. Pairs below threshold are dropped.

Standalone test:
    python function_schema/score_pair.py
"""

import os
import re
from typing import Optional

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

QUALITY_THRESHOLD = 7


class ScorePair:

    def __init__(self):
        self.name = "score_pair"
        self.description = (
            "Scores a training pair (question + response) 1–10 on relevance, "
            "quality, and training value. Returns the integer score. "
            "Call with question (str), response (str), and subject (str)."
        )
        self.client = OpenAI(
            api_key=os.getenv("HF_TOKEN"),
            base_url=os.getenv("HF_API_BASE", "https://router.huggingface.co/v1")
        )
        self.model = os.getenv("HF_MODEL", "meta-llama/Llama-3.3-70B-Instruct")

    def execute(self, question: str, response: str, subject: str) -> str:
        score = self._score(question, response, subject)
        return str(score)

    def _score(self, question: str, response: str, subject: str) -> int:
        prompt = (
            f"Subject: {subject}\n\n"
            f"Question: {question}\n"
            f"Response: {response}\n\n"
            f"Score this training pair 1–10 on:\n"
            f"- Does the question naturally lead to this response? (relevance)\n"
            f"- Is the response factual, coherent, and well-formed? (quality)\n"
            f"- Would this pair teach an LLM useful knowledge about {subject}? (value)\n\n"
            f"Return ONLY a single integer 1–10. Nothing else."
        )
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=5,
            )
            raw = resp.choices[0].message.content.strip()
            match = re.search(r"\d+", raw)
            if match:
                return min(10, max(1, int(match.group())))
        except Exception as e:
            print(f"   ⚠️  ScorePair error: {e}")
        return 0


if __name__ == "__main__":
    tool = ScorePair()
    score = tool.execute(
        question="Why did you leave Warsaw to study in Paris?",
        response=(
            "Warsaw didn't have the scientific infrastructure I needed. "
            "The Flying University was a start, but Paris had real laboratories "
            "and real freedom. I scraped together what little money I had and went."
        ),
        subject="Marie Curie"
    )
    print(f"Score: {score}/10  (threshold: {QUALITY_THRESHOLD})")