# unscramble-bench

A small, exact-answer LLM benchmark built around one idea: **chain two easy
tasks and grade the composition.** Each math question hides a short math phrase
behind scrambled letters. The model must first unscramble the letters into an
English phrase ("least common multiple of twenty four and thirty six"), then
evaluate that phrase and answer with digits. Each step looks easy in
isolation, yet the best score to date is 85% — see
[Known limitations](#known-limitations) for what that number does and doesn't
establish.

Every question has a single deterministic answer, so grading is exact string
comparison. No judge model, no partial credit.

## Results

Scores are one scored attempt per question via
[OpenRouter](https://openrouter.ai). "Failed API calls" counts requests that
never produced a model answer — transport errors, rate limits, and provider
error responses. These score zero but aren't the model's fault, so treat scores
with many failed calls as lower bounds. Models whose every request failed
(unavailable/404, out-of-credit/402, or persistent provider errors) are omitted
rather than listed as 0%.

### `low` reasoning config — current 25-question set

Combined across runs on the active 25-question
[math-scramble-puzzles.json](questions/math-scramble-puzzles.json).

| Model | Score | Correct | Failed API calls | Cost |
| --- | ---: | ---: | ---: | ---: |
| `openai/gpt-5.6-sol` | 60% | 15/25 | 0 | $1.57 |
| `openai/gpt-5.5` | 48% | 12/25 | 0 | $1.71 |
| `openai/gpt-5.6-terra` | 32% | 8/25 | 0 | $1.08 |
| `anthropic/claude-opus-4.8` | 28% | 7/25 | 0 | $1.80 |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | 28% | 7/25 | 0 | $0.00 |
| `openai/gpt-oss-120b:free` | 28% | 7/25 | 0 | $0.00 |
| `moonshotai/kimi-k2.7-code` | 20% | 5/25 | 0 | $0.33 |
| `z-ai/glm-5.2` | 20% | 5/25 | 0 | $0.26 |
| `openai/gpt-5.6-luna` | 20% | 5/25 | 0 | $0.33 |
| `openrouter/free` | 12% | 3/25 | 0 | $0.00 |
| `nvidia/nemotron-3-super-120b-a12b:free` | 8% | 2/25 | 0 | $0.00 |
| `openai/gpt-oss-20b:free` | 4% | 1/25 | 0 | $0.00 |
| `poolside/laguna-m.1:free` | 4% | 1/25 | 0 | $0.00 |
| `nvidia/nemotron-3-nano-30b-a3b:free` | 0% | 0/25 | 1 | $0.00 |
| `nvidia/nemotron-nano-12b-v2-vl:free` | 0% | 0/25 | 2 | $0.00 |

Several `low`-config misses on stronger models were empty-content responses
(reasoning tokens but no final message), so these are lower bounds; the
`high`-config runs below saw far fewer of those.

### `high` reasoning config — previous 20-question set

Older run on the 20-question version of the file (before it grew to 25
numeric-answer questions and the prompt was tightened). Kept for reference; not
directly comparable to the table above.

| Model | Score | Correct | Failed API calls | Cost |
| --- | ---: | ---: | ---: | ---: |
| `openai/gpt-5.5` | 85% | 17/20 | 3 | $5.55 |
| `qwen/qwen3.7-plus` | 50% | 10/20 | 3 | $0.44 |
| `google/gemini-3-flash-preview` | 45% | 9/20 | 1 | $1.25 |
| `google/gemma-4-31b-it` | 45% | 9/20 | 3 | $0.06 |
| `moonshotai/kimi-k2.7-code` | 45% | 9/20 | 11 | $0.63 |
| `openai/gpt-5.4-nano` | 45% | 9/20 | 11 | $0.37 |
| `mistralai/mistral-small-2603` | 40% | 8/20 | 0 | $0.22 |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | 40% | 8/20 | 0 | $0.00 |
| `qwen/qwen3.6-flash` | 40% | 8/20 | 2 | $1.05 |
| `qwen/qwen3.5-flash-02-23` | 40% | 8/20 | 3 | $0.20 |
| `nex-agi/nex-n2-pro:free` | 40% | 8/20 | 11 | $0.00 |
| `openai/gpt-5.1-codex-mini` | 40% | 8/20 | 12 | $0.84 |
| `openai/gpt-5.4-mini` | 40% | 8/20 | 12 | $1.55 |
| `google/gemini-3.1-flash-lite` | 35% | 7/20 | 2 | $0.46 |
| `openrouter/free` | 35% | 7/20 | 6 | $0.00 |
| `openai/gpt-5-nano` | 35% | 7/20 | 13 | $0.13 |
| `poolside/laguna-m.1:free` | 30% | 6/20 | 2 | $0.00 |
| `deepseek/deepseek-v3.2` | 30% | 6/20 | 7 | $0.20 |
| `anthropic/claude-opus-4.8` | 30% | 6/20 | 11 | $8.33 |
| `google/gemma-4-26b-a4b-it` | 30% | 6/20 | 13 | $0.16 |
| `minimax/minimax-m2.5` | 30% | 6/20 | 14 | $0.40 |
| `nvidia/nemotron-3-nano-30b-a3b:free` | 25% | 5/20 | 2 | $0.00 |
| `deepseek/deepseek-v3.2-exp` | 25% | 5/20 | 9 | $0.10 |
| `deepseek/deepseek-v4-flash` | 25% | 5/20 | 9 | $0.10 |
| `nvidia/nemotron-3-nano-30b-a3b` | 25% | 5/20 | 15 | $0.12 |
| `google/gemini-2.5-flash-lite-preview-09-2025` | 20% | 4/20 | 0 | $0.13 |
| `minimax/minimax-m2.7` | 20% | 4/20 | 11 | $0.44 |
| `poolside/laguna-xs.2:free` | 20% | 4/20 | 15 | $0.00 |
| `nvidia/nemotron-3-super-120b-a12b:free` | 15% | 3/20 | 0 | $0.00 |
| `nvidia/nemotron-nano-12b-v2-vl:free` | 15% | 3/20 | 3 | $0.00 |
| `moonshotai/kimi-k2.6` | 15% | 3/20 | 15 | $0.64 |
| `nvidia/nemotron-3-super-120b-a12b` | 15% | 3/20 | 16 | $0.19 |
| `openai/gpt-oss-120b:free` | 15% | 3/20 | 17 | $0.00 |
| `mistralai/mistral-small-3.2-24b-instruct` | 10% | 2/20 | 0 | $0.00 |
| `openrouter/owl-alpha` | 10% | 2/20 | 0 | $0.00 |
| `stepfun/step-3.7-flash` | 10% | 2/20 | 15 | $0.56 |
| `z-ai/glm-4.7-flash` | 10% | 2/20 | 18 | $0.20 |
| `minimax/minimax-m3` | 5% | 1/20 | 13 | $0.30 |
| `openai/gpt-4.1-nano` | 0% | 0/20 | 0 | $0.00 |
| `liquid/lfm-2.5-1.2b-instruct:free` | 0% | 0/20 | 20 | $0.00 |
| `liquid/lfm-2.5-1.2b-thinking:free` | 0% | 0/20 | 20 | $0.00 |
| `openai/gpt-oss-20b:free` | 0% | 0/20 | 20 | $0.00 |

One caveat on the top row: GPT-5.5 alone got targeted reruns of its
empty-content transport failures (the remaining misses returned reasoning
tokens but no final message content), so its row is not perfectly comparable
to the others. Results from the earlier, easier plain word-unscramble task are
archived in [original-scramble-run.csv](data/original-scramble-run.csv).

## Example question

```
Solve the math puzzle hidden behind these scrambled characters. It's not a
cipher or a way to convert characters to numbers. Unscramble the characters
into the intended English phrase, using every letter exactly once. Then solve
the math phrase as written.

ocmtrutnrle oxftluotdosne hlspattiameny iwfiym

Puzzle: Evaluate the mathematical operation in the unscrambled phrase. Write
the answer using digits, not words.
```

Hidden phrase: `least common multiple of twenty four and thirty six`. Expected
answer: `72`.

## Usage

Requires Python 3.9+ and an [OpenRouter](https://openrouter.ai) API key in
`OPENROUTER_API_KEY` (a `.env` file in the repo root is loaded automatically).

```sh
pip install -r requirements.txt

# math benchmark, one model, high reasoning
python3 main.py --models anthropic/claude-opus-4.8 --configs high

# a model group ("frontier", "cheap", "free", or "all"; see models.py)
python3 main.py --models cheap --configs low

# plain word/phrase unscrambling
python3 word_unscramble.py --models openai/gpt-5.5 --configs high

# validate a question file without making API calls
python3 main.py --questions questions/ops-reconciliation.json --validate-only
```

Each run writes a JSON report (per-attempt rows plus aggregates, including
reasoning traces and cost) under `runs/`.

Useful flags: `--runs N` repeats every question N times, `--limit N` takes the
first N questions, `--workers`, `--timeout`, and `--max-tokens` control the
request fan-out.

## Question file formats

`main.py` reads a structured file: a top-level `questions` list where each
question has an `answer` plus either its own `prompt` or fields that fill a
top-level `prompt_template`:

```json
{
  "prompt_template": "...{scrambled}...{task}...",
  "questions": [
    {"id": "arithmetic-3", "scrambled": "ene anurqsid", "task": "Evaluate...", "answer": "81"}
  ]
}
```

`word_unscramble.py` reads a compact scrambled-to-answer map:

```json
{
  "obtua": "about"
}
```

Grading: numeric answers must match exactly after whitespace/case
normalization; multi-word phrase answers additionally accept any word order
(`lurking lemons` == `lemons lurking`).

## Repo layout

- [main.py](main.py) — benchmark runner: question loading, OpenRouter calls
  with retry/backoff, exact-match scoring, JSON reports.
- [word_unscramble.py](word_unscramble.py) — thin wrapper running the plain
  unscramble task through the same runner.
- [models.py](models.py) — model groups (`frontier`, `cheap`, `free`).
- [questions/](questions) — task files; `math-scramble-puzzles.json` is the
  headline set.
- [scripts/generate_scramble_questions.py](scripts/generate_scramble_questions.py)
  — deterministic generator for the plain word-unscramble set. The math
  questions are curated by hand; the loader verifies every scramble is a true
  anagram of its hidden phrase (`--validate-only` runs this check offline).
- [scripts/generate_ops_reconciliation.py](scripts/generate_ops_reconciliation.py)
  — generator for a work-like extension: multi-rule back-office reconciliation
  tasks with a reference solver as ground truth.
- [tests/](tests) — unit tests for loading, scoring, and retry behavior
  (`python3 -m unittest discover tests`).

## Design notes

1. Early word/phrase tasks had answer-order ambiguity, so the grader
   normalizes phrases and accepts equivalent word orderings.
2. Some early "failures" were really timeout artifacts, which flattered small
   models. Harder but shorter deterministic tasks give a cleaner signal, and
   API failures are now reported separately from wrong answers.
3. Pure unscrambling saturates quickly (top models were at 93–100% on the
   original task). The scrambled-math composition restored headroom, and the
   same harness extends to realistic multi-rule work — see
   `questions/ops-reconciliation.json` for expense/payroll/inventory-style
   tasks with a reference solver as ground truth.

## Known limitations

- No ablation yet separating "can't unscramble" from "can't do the math" —
  running the same questions with the phrase disclosed would isolate the
  composition effect.
- Single scored attempt per question and no provider pinning, so OpenRouter
  routing and provider flakiness add noise; the failed-API-call column makes
  that visible but doesn't remove it.
- The leaderboard was compiled from local run reports that aren't committed
  (`runs/` is gitignored), so the table isn't independently reproducible from
  this repo alone.
