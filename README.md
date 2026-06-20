# Agent_Chameleon

An autonomous agent that researches a given subject (e.g. a public figure) and generates **persona-based LLM fine-tuning datasets**. Given a name, it discovers and scrapes relevant web sources, transforms the content into instruction–response pairs in that person's voice, scores each pair for quality, and writes the accepted pairs to a `.jsonl` file ready for fine-tuning.

Built as a modular, tool-based agent pipeline in Python.

---

## What it does

Given a subject and a target number of pairs, the agent produces a training file such as this (alpaca format):

```json
{
  "instruction": "Respond as Steve Jobs would, drawing on real knowledge and experience.",
  "input": "What's your approach to building on past successes?",
  "output": "If you do something and it turns out pretty good, then you should go do something else wonderful, not dwell on it for too long."
}
```

Three output formats are supported: `alpaca`, `sharegpt`, and `openai`.

---

## How it works

The agent runs as a multi-stage pipeline. Each stage is a self-contained "tool" in `src/function_schema/`, auto-discovered at startup by `tool_registry.py` — so the pipeline is modular and each stage can be developed or swapped independently.

```
Agent_Chameleon.py            orchestrator + interactive CLI
        │
        ├─ discover_urls      find candidate source URLs per topic        (network)
        ├─ scrape_url         fetch page text for each URL                 (network)
        ├─ chunk_and_filter   split text into chunks, dedupe via hashing
        ├─ clean_direct_quote tidy raw extracted quotes
        ├─ fix_interview_pairs turn interview transcripts into Q/A pairs    (LLM)
        ├─ transform_to_voice rewrite source chunks in the subject's voice  (LLM)
        ├─ generate_question  write a fitting question for an answer        (LLM)
        ├─ score_pair         rate each pair 0–10 for quality              (LLM)
        └─ write_output       append accepted pairs to the .jsonl file
```

**Two-phase generation:**

1. **Phase 1 — direct sources.** Uses real quotes and interview material first, as the highest-fidelity data.
2. **Phase 2 — fallback transform.** Only runs if Phase 1 didn't reach the target; rewrites general source material into the subject's voice.

A pair is only written if `score_pair` rates it at or above the quality threshold (default **7/10**), so the output is filtered for quality rather than raw volume.

---

## Project structure

```
Agent_Chameleon/
├── src/
│   ├── Agent_Chameleon.py          orchestrator + interactive CLI entry point
│   └── function_schema/
│       ├── tool_registry.py        auto-discovers and executes pipeline tools
│       ├── llm_config.py           LLM client configuration
│       ├── discover_urls.py        source URL discovery
│       ├── scrape_url.py           page scraping
│       ├── chunk_and_filter.py     chunking + deduplication
│       ├── clean_direct_quote.py   quote cleanup
│       ├── fix_interview_pairs.py  transcript → Q/A pairs
│       ├── transform_to_voice.py   rewrite content in-voice
│       ├── generate_question.py    question generation
│       ├── score_pair.py           quality scoring
│       └── write_output.py         writes the final .jsonl
├── data/output/                    generated .jsonl datasets land here
├── requirements.txt
└── .env                            API keys — NOT committed (see Setup)
```

---

## Setup

**Requirements:** Python 3.10+

```bash
# 1. Clone and enter the project
git clone https://github.com/affaanminhas/Agent_Chameleon.git
cd Agent_Chameleon

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

**Add your API key.** Create a file named `.env` in the project root:

```
GROQ_API_KEY=your_key_here
```

The project uses the Groq API by default (free tier available at [console.groq.com](https://console.groq.com)). The model and endpoint can be overridden via optional `.env` variables:

```
HF_MODEL=llama-3.3-70b-versatile
HF_API_BASE=https://api.groq.com/openai/v1
```

> `.env` is listed in `.gitignore` and should never be committed — it holds your private keys.

---

## Running

From the project root, with the virtual environment active:

```bash
python src/Agent_Chameleon.py
```

It will prompt for:

- **Subject** — the person to generate data for (e.g. `Steve Jobs`)
- **Target pairs** — how many training pairs to aim for (default `1000`)
- **Format** — `alpaca`, `sharegpt`, or `openai` (default `alpaca`)

The output is written to `data/output/<subject_name>.jsonl`.

---

## Configuration

Key settings live at the top of `src/Agent_Chameleon.py`:

| Setting             | Default                  | Purpose                                  |
|---------------------|--------------------------|------------------------------------------|
| `QUALITY_THRESHOLD` | `7`                      | Minimum score (0–10) to keep a pair      |
| `REQUEST_DELAY`     | `1.0`                    | Delay (seconds) between source fetches   |
| `MAX_RETRIES`       | `2`                      | Retry attempts on a failed stage         |
| `MODEL_NAME`        | `llama-3.3-70b-versatile`| LLM model (from `.env`)                  |

---

## Design notes

- **Tool-based architecture.** Each pipeline stage is an independent, auto-discovered tool. Adding or replacing a stage means adding a file to `function_schema/` — no changes to the orchestrator.
- **Quality-gated output.** Every pair is scored by the LLM and dropped if it falls below the threshold, so the dataset favours quality over quantity.
- **Graceful failure.** Network stages use timeouts and per-topic error handling, so one unreachable source can't abort an entire run.

---

## Notes & limitations

- **Search reachability.** Source discovery scrapes public search/encyclopedia endpoints, which can rate-limit or block automated traffic under volume. For large runs, running behind a VPN or from a cloud VM avoids most per-site reachability issues.
- **Generated data is for fine-tuning experimentation.** Output quality depends on the availability and quality of public source material for the chosen subject.

---

## License

This project is provided for portfolio and educational purposes.