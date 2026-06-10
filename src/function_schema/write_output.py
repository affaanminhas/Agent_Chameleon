"""
Write Output Tool
Path: function_schema/write_output.py

Writes a completed training pair to a .jsonl file in the
requested format: alpaca, sharegpt, or openai.

Standalone test:
    python function_schema/write_output.py
"""

import os
import json
from datetime import datetime
from typing import Dict


FORMATS = ["alpaca", "sharegpt", "openai"]
OUTPUT_DIR = "./data/output"

INSTRUCTION_VARIANTS = [
    "You are knowledgeable about {subject}. Answer the question accurately and naturally.",
    "Respond as {subject} would, drawing on real knowledge and experience.",
    "Answer this question about {subject} in an informative, natural way.",
    "You have deep expertise on {subject}. Share your knowledge clearly.",
    "Respond authentically about {subject}, based on real facts and experience.",
]


class WriteOutput:

    def __init__(self):
        self.name = "write_output"
        self.description = (
            "Writes a training pair to a .jsonl file in alpaca, sharegpt, or openai format. "
            "Call with question (str), response (str), subject (str), "
            "output_format (str), output_path (str), and pair_index (int)."
        )

    def execute(
        self,
        question: str,
        response: str,
        subject: str,
        output_format: str,
        output_path: str,
        pair_index: int = 0,
    ) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        pair = self._format(question, response, subject, output_format, pair_index)

        with open(output_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")

        return f"Written pair {pair_index} to {output_path}"

    def _format(
        self,
        question: str,
        response: str,
        subject: str,
        fmt: str,
        idx: int,
    ) -> Dict:
        instruction = INSTRUCTION_VARIANTS[idx % len(INSTRUCTION_VARIANTS)].format(
            subject=subject
        )

        if fmt == "alpaca":
            return {
                "instruction": instruction,
                "input": question,
                "output": response,
            }

        elif fmt == "sharegpt":
            return {
                "conversations": [
                    {"from": "system",  "value": instruction},
                    {"from": "human",   "value": question},
                    {"from": "gpt",     "value": response},
                ]
            }

        elif fmt == "openai":
            return {
                "messages": [
                    {"role": "system",    "content": instruction},
                    {"role": "user",      "content": question},
                    {"role": "assistant", "content": response},
                ]
            }

        else:
            raise ValueError(f"Unknown format '{fmt}'. Choose: {FORMATS}")


if __name__ == "__main__":
    tool = WriteOutput()
    for fmt in FORMATS:
        path = f"./data/output/test_{fmt}.jsonl"
        result = tool.execute(
            question="Why did you move to Paris?",
            response="Warsaw couldn't offer what I needed. Paris had the labs.",
            subject="Marie Curie",
            output_format=fmt,
            output_path=path,
            pair_index=0,
        )
        print(result)