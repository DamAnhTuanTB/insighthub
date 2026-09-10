import contextlib
import io
import json
import unittest
from unittest.mock import patch

from app.core.errors import ProviderError
from arq import Retry
from worker import LOGGING_CONFIG, ingest_document


class WorkerTaskTests(unittest.IsolatedAsyncioTestCase):
    def test_arq_argument_logging_is_disabled(self):
        logger = LOGGING_CONFIG["loggers"]["arq.worker"]
        self.assertEqual(logger["level"], "CRITICAL")
        self.assertFalse(logger["propagate"])

    async def test_transient_failure_retries_with_exponential_delay(self):
        for attempt, expected_delay in ((1, 1), (2, 2)):
            output = io.StringIO()
            with (
                patch("worker.process_document", side_effect=ProviderError()),
                contextlib.redirect_stdout(output),
                self.assertRaises(Retry) as raised,
            ):
                await ingest_document(
                    {"job_try": attempt}, 17, "private.txt", b"private content"
                )
            self.assertEqual(raised.exception.defer_score, expected_delay * 1000)
            event = json.loads(output.getvalue())
            self.assertEqual(event["event"], "ingestion_retry")
            self.assertNotIn("private", output.getvalue())

    async def test_third_failure_is_terminal_and_sanitized(self):
        output = io.StringIO()
        with (
            patch("worker.process_document", side_effect=ProviderError()),
            contextlib.redirect_stdout(output),
            self.assertRaises(ProviderError),
        ):
            await ingest_document({"job_try": 3}, 18, "private.txt", b"private content")
        event = json.loads(output.getvalue())
        self.assertEqual(event["event"], "ingestion_failed")
        self.assertEqual(event["error_code"], "provider_error")
        self.assertNotIn("private", output.getvalue())

    async def test_success_emits_verifier_completion_contract(self):
        output = io.StringIO()
        with (
            patch("worker.process_document", return_value=2),
            contextlib.redirect_stdout(output),
        ):
            result = await ingest_document(
                {"job_try": 1}, 19, "private.txt", b"private content"
            )
        event = json.loads(output.getvalue())
        self.assertEqual(result, 2)
        self.assertEqual(
            (event["event"], event["document_id"], event["status"]),
            ("ingestion_completed", 19, "ready"),
        )
        self.assertTrue(event["timestamp"].endswith("Z"))


if __name__ == "__main__":
    unittest.main()
