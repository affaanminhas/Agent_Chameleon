"""
Transform to Voice Tool
Path: function_schema/transform_to_voice.py

Rewrites a raw text chunk into a natural response as if spoken
by the subject (first person for people) or a domain expert
(for topics). Uses the LLM.

Standalone test:
    python function_schema/transform_to_voice.py
"""

import os
import re
from typing import Optional

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class TransformToVoice:

    def __init__(self):
        self.name = "transform_to_voice"
        self.description = (
            "Rewrites a raw text chunk into a natural, first-person response "
            "as if spoken by the subject. Removes third-person references. "
            "Call with chunk (str) and subject (str). Returns transformed text."
        )
        self.client = OpenAI(
            api_key=os.getenv("HF_TOKEN"),
            base_url=os.getenv("HF_API_BASE", "https://router.huggingface.co/v1")
        )
        self.model = os.getenv("HF_MODEL", "meta-llama/Llama-3.3-70B-Instruct")

    def execute(self, chunk: str, subject: str) -> str:
        result = self._transform(chunk, subject)
        return result or ""

    def _transform(self, chunk: str, subject: str) -> Optional[str]:
        prompt = (
            f"Subject: {subject}\n\n"
            f"Raw source text:\n{chunk}\n\n"
            f"Task: Rewrite this as a natural response that could be given by or about "
            f"{subject}. If {subject} is a person, write in first person as that person "
            f"speaking from their own experience. If {subject} is a topic or domain, "
            f"write as a knowledgeable expert explaining it clearly.\n\n"
            f"Requirements:\n"
            f"- Sound natural and conversational, not encyclopaedic\n"
            f"- Keep all factual content — do not invent anything\n"
            f"- Remove third-person references like '{subject} said' — speak directly\n"
            f"- 2–5 sentences. Substantive but not exhaustive.\n"
            f"- Return ONLY the response text. No preamble."
        )
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=300,
            )
            result = resp.choices[0].message.content.strip()
            if len(result.split()) >= 20:
                return result
        except Exception as e:
            print(f"   ⚠️  TransformToVoice error: {e}")
        return None


if __name__ == "__main__":
    chunk = (
        "Marie Curie was born in Warsaw in 1867. She moved to Paris in 1891 to study "
        "physics and chemistry. She became the first woman to win a Nobel Prize, "
        "receiving the award in physics in 1903 and chemistry in 1911."
    )
    tool   = TransformToVoice()
    result = tool.execute(chunk=chunk, subject="Marie Curie")
    print(result)