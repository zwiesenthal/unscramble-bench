import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import main
import word_unscramble


def write_json(payload):
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False)
    with handle:
        json.dump(payload, handle)
    return Path(handle.name)


class QuestionLoaderTests(unittest.TestCase):
    def test_structured_loader_accepts_task_only_template(self):
        path = write_json({
            "prompt_template": "{task}\nReturn JSON.",
            "questions": [
                {"id": "q1", "task": "Compute 2+2.", "answer": 4},
            ],
        })
        try:
            questions = main.load_questions(path)
        finally:
            path.unlink()

        self.assertEqual(questions[0]["id"], "q1")
        self.assertEqual(questions[0]["scrambled"], "")
        self.assertEqual(questions[0]["answer"], "4")
        self.assertIn("Compute 2+2.", questions[0]["prompt"])

    def test_structured_loader_reports_missing_template_field(self):
        path = write_json({
            "prompt_template": "{missing}",
            "questions": [
                {"id": "q1", "answer": "x"},
            ],
        })
        try:
            with self.assertRaisesRegex(ValueError, "missing field 'missing'"):
                main.load_questions(path)
        finally:
            path.unlink()

    def test_structured_loader_rejects_duplicate_ids(self):
        path = write_json({
            "prompt_template": "{task}",
            "questions": [
                {"id": "q1", "task": "A", "answer": "a"},
                {"id": "q1", "task": "B", "answer": "b"},
            ],
        })
        try:
            with self.assertRaisesRegex(ValueError, "duplicate question id"):
                main.load_questions(path)
        finally:
            path.unlink()

    def test_structured_loader_rejects_non_anagram_scramble(self):
        path = write_json({
            "prompt_template": "{scrambled} {task}",
            "questions": [
                {
                    "id": "q1",
                    "scrambled": "ene anurqsid",
                    "phrase": "nine cubed",
                    "task": "Evaluate.",
                    "answer": "729",
                },
            ],
        })
        try:
            with self.assertRaisesRegex(ValueError, "not an anagram"):
                main.load_questions(path)
        finally:
            path.unlink()

    def test_word_loader_accepts_flat_map_and_generated_wrapper(self):
        flat_path = write_json({"obtua": "about"})
        wrapped_path = write_json({"metadata": {"seed": 1}, "questions": {"cchou": "couch"}})
        try:
            self.assertEqual(word_unscramble.load_questions(flat_path)[0]["answer"], "about")
            self.assertEqual(word_unscramble.load_questions(wrapped_path)[0]["answer"], "couch")
        finally:
            flat_path.unlink()
            wrapped_path.unlink()


class ScoringTests(unittest.TestCase):
    def test_phrase_scoring_ignores_order_case_and_extra_whitespace(self):
        self.assertTrue(main.is_correct("  LURKING   lemons ", "lemons lurking"))

    def test_numeric_format_still_matters(self):
        self.assertFalse(main.is_correct("931.7", "931.70"))

    def test_parse_model_answer_accepts_plain_or_fenced_json(self):
        self.assertEqual(main.parse_model_answer('{"answer": "42"}'), "42")
        self.assertEqual(main.parse_model_answer('```json\n{"answer": "42"}\n```'), "42")

    def test_score_attempt_preserves_malformed_response_as_error(self):
        row = main.score_attempt(
            "model",
            "low",
            1,
            {"id": "q1", "prompt": "p", "answer": "42"},
            {},
            0.1,
            None,
        )

        self.assertFalse(row["correct"])
        self.assertIn("malformed response", row["error"])

    def test_score_attempt_logs_reasoning_fields(self):
        response = {
            "model": "provider/model",
            "choices": [
                {
                    "message": {
                        "content": '{"answer": "42"}',
                        "reasoning": "computed directly",
                        "reasoning_details": [{"type": "summary", "text": "2+40"}],
                    },
                    "reasoning": "choice-level notes",
                    "finish_reason": "stop",
                }
            ],
            "usage": {"cost": 0.01},
        }

        row = main.score_attempt(
            "model",
            "high",
            1,
            {"id": "q1", "prompt": "p", "answer": "42"},
            response,
            0.1,
            None,
        )

        self.assertTrue(row["correct"])
        self.assertEqual(row["reasoning"]["message.reasoning"], "computed directly")
        self.assertEqual(row["reasoning"]["choice.reasoning"], "choice-level notes")
        self.assertEqual(row["response_message"]["content"], '{"answer": "42"}')
        self.assertEqual(row["response_choice"]["finish_reason"], "stop")

    def test_reasoning_without_content_is_failed_attempt_not_api_failure(self):
        response = {
            "model": "provider/model",
            "choices": [
                {
                    "message": {
                        "content": None,
                        "reasoning": "I found the answer but did not emit JSON.",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"cost": 0.01},
        }

        row = main.score_attempt(
            "model",
            "high",
            1,
            {"id": "q1", "prompt": "p", "answer": "42"},
            response,
            0.1,
            None,
        )

        self.assertFalse(row["correct"])
        self.assertFalse(row["api_error"])
        self.assertEqual(row["error"], "malformed response: empty message content")
        self.assertEqual(main.aggregate([row])[0]["failed_api_calls"], 0)

    def test_error_body_with_http_200_counts_as_api_failure(self):
        response = {"error": {"code": 429, "message": "rate limited"}}

        row = main.score_attempt(
            "model",
            "high",
            1,
            {"id": "q1", "prompt": "p", "answer": "42"},
            response,
            0.1,
            None,
        )

        self.assertFalse(row["correct"])
        self.assertTrue(row["api_error"])

    def test_internal_server_error_counts_as_api_failure(self):
        response = {"error": {"code": 500, "message": "Internal Server Error"}}

        row = main.score_attempt(
            "model",
            "high",
            1,
            {"id": "q1", "prompt": "p", "answer": "42"},
            response,
            0.1,
            None,
        )

        self.assertFalse(row["correct"])
        self.assertTrue(row["api_error"])
        self.assertEqual(main.aggregate([row])[0]["failed_api_calls"], 1)

    def run_attempt_against(self, responses):
        class FakeResponse:
            text = ""

            def __init__(self, payload, status_code=200):
                self.payload = payload
                self.status_code = status_code

            def json(self):
                return self.payload

        class FakeSession:
            def __init__(self):
                self.calls = 0

            def post(self, *args, **kwargs):
                response = responses[min(self.calls, len(responses) - 1)]
                self.calls += 1
                return FakeResponse(*response)

        original_sleep = main.time.sleep
        try:
            main.time.sleep = lambda _seconds: None
            session = FakeSession()
            row = main.run_attempt(
                session,
                "model",
                "high",
                1,
                {"id": "q1", "prompt": "p", "answer": "42"},
                timeout=1,
                max_tokens=None,
            )
        finally:
            main.time.sleep = original_sleep

        return session.calls, row

    SUCCESS_BODY = {
        "model": "provider/model",
        "choices": [{"message": {"content": '{"answer": "42"}'}}],
        "usage": {"cost": 0.01},
    }

    def test_run_attempt_retries_internal_server_errors(self):
        error_body = {"error": {"code": 500, "message": "Internal Server Error"}}
        calls, row = self.run_attempt_against([
            (error_body,),
            (error_body,),
            (self.SUCCESS_BODY,),
        ])

        self.assertEqual(calls, 3)
        self.assertTrue(row["correct"])
        self.assertFalse(row["api_error"])

    def test_run_attempt_retries_http_429_then_succeeds(self):
        calls, row = self.run_attempt_against([
            ({"error": {"message": "rate limited"}}, 429),
            (self.SUCCESS_BODY,),
        ])

        self.assertEqual(calls, 2)
        self.assertTrue(row["correct"])
        self.assertFalse(row["api_error"])

    def test_run_attempt_retries_non_json_429_then_succeeds(self):
        class NonJsonResponse:
            status_code = 429
            text = "slow down"

            def json(self):
                raise ValueError("not json")

        responses = [NonJsonResponse(), None]

        class FakeSession:
            def __init__(self):
                self.calls = 0

            def post(self, *args, **kwargs):
                response = responses[min(self.calls, len(responses) - 1)]
                self.calls += 1
                if response is None:
                    return self._success()
                return response

            @staticmethod
            def _success():
                class Success:
                    status_code = 200
                    text = ""

                    def json(self):
                        return ScoringTests.SUCCESS_BODY

                return Success()

        original_sleep = main.time.sleep
        try:
            main.time.sleep = lambda _seconds: None
            session = FakeSession()
            row = main.run_attempt(
                session,
                "model",
                "high",
                1,
                {"id": "q1", "prompt": "p", "answer": "42"},
                timeout=1,
                max_tokens=None,
            )
        finally:
            main.time.sleep = original_sleep

        self.assertEqual(session.calls, 2)
        self.assertTrue(row["correct"])
        self.assertFalse(row["api_error"])

    def test_run_attempt_treats_http_400_as_api_failure_without_retry(self):
        calls, row = self.run_attempt_against([
            ({"error": {"message": "invalid model"}}, 400),
        ])

        self.assertEqual(calls, 1)
        self.assertFalse(row["correct"])
        self.assertTrue(row["api_error"])
        self.assertIn("HTTP 400", row["error"])


class CliTests(unittest.TestCase):
    def test_missing_models_is_an_error_exit(self):
        path = write_json({
            "prompt_template": "{task}",
            "questions": [{"id": "q1", "task": "Compute 2+2.", "answer": "4"}],
        })
        try:
            with redirect_stdout(StringIO()):
                result = main.main(["--questions", str(path)])
            self.assertEqual(result, 1)
        finally:
            path.unlink()

    def test_validate_only_does_not_require_api_key(self):
        path = write_json({
            "prompt_template": "{task}",
            "questions": [{"id": "q1", "task": "Compute 2+2.", "answer": "4"}],
        })
        old_key = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            args = main.parse_args(
                ["--questions", str(path), "--validate-only"],
                "test runner",
                str(path),
                "test-results",
            )
            with redirect_stdout(StringIO()):
                result = main.run_benchmark(args, main.load_questions(path))
            self.assertEqual(result, 0)
        finally:
            if old_key is not None:
                os.environ["OPENROUTER_API_KEY"] = old_key
            path.unlink()


if __name__ == "__main__":
    unittest.main()
