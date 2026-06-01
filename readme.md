AI benchmark to test the ability to unscramble words and phrases.

All words are scrabble legal.

If an input has multiple words the ordering of the words doesn't matter (ex. lurking lemons == lemons lurking).

## Benchmark Results

Results using the `high` config.

| Model | Score | Correct | Failed API Calls |
| --- | ---: | ---: | ---: |
| google/gemini-3.5-flash | 100.00% | 31/31 | 0 |
| anthropic/claude-opus-4.7 | 96.77% | 30/31 | 1 |
| openai/gpt-5.5 | 96.77% | 30/31 | 1 |
| anthropic/claude-opus-4.8 | 93.55% | 29/31 | 2 |
| google/gemini-3.1-pro-preview | 93.55% | 29/31 | 2 |
| moonshotai/kimi-k2.6 | 93.55% | 29/31 | 2 |
| openai/gpt-5.4 | 93.55% | 29/31 | 2 |
| openai/gpt-5.4-mini | 93.55% | 29/31 | 2 |
| openai/gpt-5-nano | 93.55% | 29/31 | 2 |
| qwen/qwen3.7-max | 93.55% | 29/31 | 2 |
| x-ai/grok-4.3 | 93.55% | 29/31 | 1 |
| deepseek/deepseek-v3.2-exp | 90.32% | 28/31 | 3 |
| google/gemma-4-26b-a4b-it | 87.10% | 27/31 | 4 |
| google/gemini-2.5-flash-lite-preview-09-2025 | 87.10% | 27/31 | 2 |
| qwen/qwen3.5-flash-02-23 | 87.10% | 27/31 | 4 |
| deepseek/deepseek-v4-flash | 83.87% | 26/31 | 2 |
| openai/gpt-oss-120b:free | 64.52% | 20/31 | 3 |
| openrouter/owl-alpha | 51.61% | 16/31 | 1 |
| openai/gpt-oss-20b:free | 41.94% | 13/31 | 7 |
| google/gemma-4-31b-it | 32.26% | 10/31 | 7 |
| openai/gpt-4.1-nano | 22.58% | 7/31 | 0 |
| mistralai/mistral-small-3.2-24b-instruct | 16.13% | 5/31 | 0 |
