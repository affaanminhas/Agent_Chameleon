"""
Generate Question Tool
Path: function_schema/generate_question.py

Generates the single most natural question that would prompt
a given response. Uses the LLM.

Standalone test:
    python function_schema/generate_question.py
"""

import os
import re
from typing import Optional

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class GenerateQuestion:

    def __init__(self):
        self.name = "generate_question"
        self.description = (
            "Generates the single most natural question that would prompt a given "
            "response in conversation. Call with response (str) and subject (str). "
            "Returns a question string."
        )
        self.client = OpenAI(
            api_key=os.getenv("HF_TOKEN"),
            base_url=os.getenv("HF_API_BASE", "https://router.huggingface.co/v1")
        )
        self.model = os.getenv("HF_MODEL", "meta-llama/Llama-3.3-70B-Instruct")

    def execute(self, response: str, subject: str) -> str:
        result = self._generate(response, subject)
        return result or ""

    def _generate(self, response: str, subject: str) -> Optional[str]:
        prompt = (
            f"Subject: {subject}\n\n"
            f"Response:\n{response}\n\n"
            f"Task: Write the single most natural, open-ended question that someone "
            f"would ask in a conversation or interview to receive this exact response.\n\n"
            f"Requirements:\n"
            f"- One question only\n"
            f"- No meta-references like 'based on the text' or 'according to'\n"
            f"- Conversational tone\n"
            f"- Return ONLY the question. No preamble."
        )
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=80,
            )
            raw = resp.choices[0].message.content.strip()
            # Clean up numbering or quotes
            q = re.sub(r'^[\"\'\d\.\)\-\s]+', "", raw).strip('"\'')
            if q and not q.endswith("?"):
                q += "?"
            return q if len(q) > 10 else None
        except Exception as e:
            print(f"   ⚠️  GenerateQuestion error: {e}")
        return None


if __name__ == "__main__":
    response = (
        "I moved to Paris in 1891 because Warsaw simply didn't offer the scientific "
        "education I needed. The Flying University gave me a foundation, but Paris had "
        "the laboratories and the freedom to pursue serious research. It wasn't easy — "
        "I had very little money and the winters were brutal — but I knew it was the "
        "only path forward."
    )
    tool   = GenerateQuestion()
    result = tool.execute(response=response, subject="Marie Curie")
    print(result)