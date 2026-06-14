import json
import sys
from pathlib import Path

import main as benchmark


DEFAULT_QUESTIONS = "questions/unique-unscrambles.json"
QUESTION_PROMPT = (
    "Unscramble the following letters into the intended English word or phrase. "
    "Use every letter exactly once. Return only JSON like {{\"answer\": \"...\"}}.\n\n"
    "Scrambled letters: '{scrambled}'"
)


def load_questions(path):
    questions = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        {
            "id": i,
            "scrambled": scrambled,
            "prompt": QUESTION_PROMPT.format(scrambled=scrambled),
            "answer": answer,
        }
        for i, (scrambled, answer) in enumerate(questions.items())
    ]


def main(argv=None):
    args = benchmark.parse_args(
        argv or sys.argv[1:],
        description="Run the word unscramble benchmark.",
        default_questions=DEFAULT_QUESTIONS,
        default_out_prefix="word-unscramble-results",
    )
    questions = load_questions(args.questions)
    return benchmark.run_benchmark(args, questions)


if __name__ == "__main__":
    main()
