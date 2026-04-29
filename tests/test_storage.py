"""Unit tests for p2p_chat.storage."""

import unittest

from p2p_chat.security import create_message
from p2p_chat.storage import MessageStore


def _make_store() -> MessageStore:
    return MessageStore(db_path=":memory:")


class TestMessageStore(unittest.TestCase):
    def test_save_and_retrieve(self):
        store = _make_store()
        msg = create_message("chat", "Alice", "hello")
        store.save(msg)
        recent = store.get_recent()
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["id"], msg["id"])

    def test_duplicate_save_ignored(self):
        store = _make_store()
        msg = create_message("chat", "Alice", "hello")
        store.save(msg)
        store.save(msg)  # second insert should be silently ignored
        self.assertEqual(store.count(), 1)

    def test_only_chat_returned_by_get_recent(self):
        store = _make_store()
        store.save(create_message("chat", "Alice", "hi"))
        store.save(create_message("join", "Bob", "joining"))
        store.save(create_message("leave", "Charlie", "bye"))
        recent = store.get_recent()
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["type"], "chat")

    def test_chronological_order(self):
        store = _make_store()
        msgs = [create_message("chat", "Alice", f"msg {i}") for i in range(5)]
        for m in msgs:
            store.save(m)
        recent = store.get_recent()
        timestamps = [m["timestamp"] for m in recent]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_limit_respected(self):
        store = _make_store()
        for i in range(20):
            store.save(create_message("chat", "Alice", f"msg {i}"))
        recent = store.get_recent(limit=5)
        self.assertEqual(len(recent), 5)

    def test_count_includes_all_types(self):
        store = _make_store()
        store.save(create_message("chat", "Alice", "hi"))
        store.save(create_message("join", "Bob", "joining"))
        self.assertEqual(store.count(), 2)

    def test_round_trip_preserves_fields(self):
        store = _make_store()
        msg = create_message("chat", "Dave", "round trip test")
        store.save(msg)
        retrieved = store.get_recent()[0]
        for key in ("id", "type", "sender", "content", "signature"):
            self.assertEqual(retrieved[key], msg[key])
        self.assertAlmostEqual(retrieved["timestamp"], msg["timestamp"], places=3)


if __name__ == "__main__":
    unittest.main()
