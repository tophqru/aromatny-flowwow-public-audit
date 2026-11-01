import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from image_queue import ImageQueue

def route():return SimpleNamespace(request=object(),continue_=Mock(),abort=Mock())

class ImageQueueTests(unittest.TestCase):
    def test_burst_never_dispatches_more_than_three(self):
        queue=ImageQueue();routes=[route() for _ in range(9)]
        for r in routes:queue.admit(r)
        self.assertEqual(sum(r.continue_.call_count for r in routes),3)
        self.assertEqual(queue.snapshot()['queued'],6)
        for r in routes:
            queue.finished(r.request)
            self.assertLessEqual(len(queue.active),3)
        self.assertEqual(queue.snapshot()['completed'],9)
        self.assertEqual(queue.peak,3)
    def test_unknown_completion_does_not_release_a_slot(self):
        queue=ImageQueue();routes=[route() for _ in range(4)]
        for r in routes:queue.admit(r)
        queue.finished(object())
        routes[3].continue_.assert_not_called()
    def test_cancelled_queued_request_is_never_dispatched_later(self):
        queue=ImageQueue(limit=1);active,cancelled,next_live=[route() for _ in range(3)]
        for r in (active,cancelled,next_live):queue.admit(r)
        # Closing a seller popup can fail requests before their queued route runs.
        queue.finished(cancelled.request)
        queue.finished(active.request)
        cancelled.continue_.assert_not_called()
        next_live.continue_.assert_called_once()
        self.assertEqual(queue.active,{next_live.request})
    def test_all_queued_requests_can_cancel_without_occupying_slots(self):
        queue=ImageQueue();routes=[route() for _ in range(9)]
        for r in routes:queue.admit(r)
        for r in routes[3:]:queue.finished(r.request)
        self.assertEqual(queue.snapshot()['queued'],0)
        for r in routes[:3]:queue.finished(r.request)
        self.assertEqual(queue.snapshot()['inflight'],0)
        self.assertEqual(queue.snapshot()['started'],3)
        for r in routes[3:]:r.continue_.assert_not_called()
    def test_failed_dispatch_releases_slot_without_retry(self):
        queue=ImageQueue();bad=route();bad.continue_.side_effect=RuntimeError('closed')
        queue.admit(bad)
        self.assertEqual(queue.snapshot()['inflight'],0)
        self.assertEqual(queue.errors,1)
        bad.continue_.assert_called_once();bad.abort.assert_called_once()
    def test_close_does_not_start_pending_requests(self):
        queue=ImageQueue();routes=[route() for _ in range(5)]
        for r in routes:queue.admit(r)
        queue.close();queue.finished(routes[0].request)
        routes[3].continue_.assert_not_called();routes[4].continue_.assert_not_called()
        extra=route();queue.admit(extra);extra.abort.assert_called_once()
    def test_limit_cannot_exceed_owner_ceiling(self):
        for value in (0,4,5,True):
            with self.assertRaises(ValueError):ImageQueue(value)

if __name__=='__main__':unittest.main()
