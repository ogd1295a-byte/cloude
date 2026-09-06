import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import check_certificate as monitor


def page(status, title=monitor.COURSE_TITLE):
    return (
        f'<main><div class="page"><div class="view">'
        f'<div class="headline">{title}</div>'
        f'<summary><span>{status}</span></summary>'
        '</div></div></main>'
    )


class StatusTests(unittest.TestCase):
    def test_ready(self):
        self.assertEqual(monitor.parse_status(page(monitor.READY)), monitor.READY)

    def test_waiting_ignores_ready_text_elsewhere(self):
        html = page("全班成績尚未送達") + f'<footer>{monitor.READY}</footer>'
        self.assertEqual(monitor.parse_status(html), "全班成績尚未送達")

    def test_wrong_course_or_broken_page(self):
        for html in (page(monitor.READY, "其他課程"), "<h1>Service unavailable</h1>", page("")):
            with self.subTest(html=html), self.assertRaises(ValueError):
                monitor.parse_status(html)


class NotificationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.state = Path(directory.name) / "state" / "notified.json"

    @patch.object(monitor, "notify")
    @patch.object(monitor, "fetch_page", return_value=page("全班成績尚未送達"))
    def test_waiting_records_every_check_without_notifying(self, fetch, notify):
        monitor.check(self.state)
        monitor.check(self.state)
        notify.assert_not_called()
        self.assertFalse(json.loads(self.state.read_text())["notified"])
        history = self.state.with_name("history.jsonl").read_text().splitlines()
        self.assertEqual(len(history), 2)
        self.assertEqual(json.loads(history[0])["status"], "全班成績尚未送達")

    @patch.object(monitor, "notify")
    @patch.object(monitor, "fetch_page", return_value=page(monitor.READY))
    def test_ready_notifies_only_once(self, fetch, notify):
        monitor.check(self.state)
        monitor.check(self.state)
        notify.assert_called_once_with()
        self.assertEqual(fetch.call_count, 2)
        self.assertTrue(json.loads(self.state.read_text())["notified"])
        self.assertFalse(json.loads(self.state.read_text())["last_check"]["notified_this_run"])

    @patch.object(monitor, "notify", side_effect=OSError("ntfy unavailable"))
    @patch.object(monitor, "fetch_page", return_value=page(monitor.READY))
    def test_failed_notification_is_retried_next_run(self, fetch, notify):
        with self.assertRaises(OSError):
            monitor.check(self.state)
        failed = json.loads(self.state.read_text())
        self.assertFalse(failed["notified"])
        self.assertEqual(failed["last_check"]["result"], "error")
        notify.side_effect = None
        monitor.check(self.state)
        self.assertEqual(notify.call_count, 2)

    @patch.object(monitor, "notify")
    @patch.object(monitor, "fetch_page", return_value=page(monitor.READY))
    def test_fetch_failure_preserves_notification_and_records_error(self, fetch, notify):
        monitor.check(self.state)
        fetch.side_effect = OSError("site unavailable")
        with self.assertRaises(OSError):
            monitor.check(self.state)
        receipt = json.loads(self.state.read_text())
        self.assertTrue(receipt["notified"])
        self.assertIsNone(receipt["last_check"]["status"])
        self.assertEqual(receipt["last_check"]["error"], "site unavailable")
        notify.assert_called_once_with()

    @patch.dict("os.environ", {"GITHUB_REPOSITORY": "example/monitor", "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2"})
    @patch.object(monitor, "fetch_page", return_value=page("全班成績尚未送達"))
    def test_run_link_is_recorded(self, fetch):
        monitor.check(self.state)
        record = json.loads(self.state.read_text())["last_check"]
        self.assertEqual(record["run_url"], "https://github.com/example/monitor/actions/runs/123")
        self.assertEqual(record["run_attempt"], "2")

    @patch.object(monitor, "notify")
    @patch.object(monitor, "fetch_page", return_value=page(monitor.READY))
    def test_dry_run_does_not_notify_or_save(self, fetch, notify):
        monitor.check(self.state, dry_run=True)
        notify.assert_not_called()
        self.assertFalse(self.state.exists())

    @patch.object(monitor, "urlopen")
    def test_notification_payload_and_receipt(self, urlopen):
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = json.dumps({"event": "message", "topic": monitor.TOPIC, "id": "test"}).encode()
        monitor.notify()
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["topic"], "aip479cert")
        self.assertEqual(payload["click"], monitor.COURSE_URL)
        self.assertIn(monitor.READY, payload["message"])
        response.read.return_value = b'{}'
        with self.assertRaises(ValueError):
            monitor.notify()
