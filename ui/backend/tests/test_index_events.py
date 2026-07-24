from __future__ import annotations

import unittest

from dpo.indexer.events import ProjectEventHub


class ProjectEventHubTests(unittest.TestCase):
    def test_publish_and_unsubscribe(self) -> None:
        hub = ProjectEventHub()
        queue = hub.subscribe()
        hub.publish({"changed": ["a.py"]})
        event = queue.get_nowait()
        self.assertEqual(event["event"], "project_index_updated")
        self.assertEqual(event["payload"]["changed"], ["a.py"])
        hub.unsubscribe(queue)
        hub.publish({"changed": ["b.py"]})
        self.assertTrue(queue.empty())

    def test_slow_subscriber_keeps_latest_events_bounded(self) -> None:
        hub = ProjectEventHub()
        queue = hub.subscribe()
        for index in range(40):
            hub.publish({"number": index})
        self.assertLessEqual(queue.qsize(), 32)
        values = []
        while not queue.empty():
            values.append(queue.get_nowait()["payload"]["number"])
        self.assertEqual(values[-1], 39)


if __name__ == "__main__":
    unittest.main()
