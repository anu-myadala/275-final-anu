"""Unit tests for p2p_chat.security."""

import json
import time
import unittest

from p2p_chat.security import (
    DEFAULT_SECRET,
    _canonical,
    create_message,
    sign_message,
    verify_message,
)


class TestCanonical(unittest.TestCase):
    def test_excludes_signature_field(self):
        msg = {"id": "1", "type": "chat", "signature": "abc"}
        payload = _canonical(msg)
        data = json.loads(payload.decode())
        self.assertNotIn("signature", data)

    def test_sorted_keys(self):
        msg = {"z": 1, "a": 2, "m": 3}
        payload = _canonical(msg).decode()
        # Keys should appear in alphabetical order.
        self.assertLess(payload.index('"a"'), payload.index('"m"'))
        self.assertLess(payload.index('"m"'), payload.index('"z"'))

    def test_deterministic(self):
        msg = {"id": "x", "sender": "Alice", "content": "hello"}
        self.assertEqual(_canonical(msg), _canonical(msg))


class TestSignAndVerify(unittest.TestCase):
    def _make_msg(self) -> dict:
        return create_message("chat", "Alice", "hello world")

    def test_valid_signature_passes(self):
        msg = self._make_msg()
        self.assertTrue(verify_message(msg))

    def test_missing_signature_fails(self):
        msg = self._make_msg()
        del msg["signature"]
        self.assertFalse(verify_message(msg))

    def test_tampered_content_fails(self):
        msg = self._make_msg()
        msg["content"] = "evil content"
        self.assertFalse(verify_message(msg))

    def test_tampered_sender_fails(self):
        msg = self._make_msg()
        msg["sender"] = "Mallory"
        self.assertFalse(verify_message(msg))

    def test_wrong_secret_fails(self):
        msg = self._make_msg()
        self.assertFalse(verify_message(msg, secret=b"wrong-secret"))

    def test_custom_secret(self):
        secret = b"my-custom-secret"
        msg = create_message("chat", "Bob", "hi", secret=secret)
        self.assertTrue(verify_message(msg, secret=secret))
        self.assertFalse(verify_message(msg, secret=DEFAULT_SECRET))


class TestCreateMessage(unittest.TestCase):
    def test_required_fields_present(self):
        msg = create_message("chat", "Alice", "hi")
        for field in ("id", "type", "sender", "timestamp", "content", "peers", "signature"):
            self.assertIn(field, msg)

    def test_type_and_sender(self):
        msg = create_message("join", "Bob", "joining")
        self.assertEqual(msg["type"], "join")
        self.assertEqual(msg["sender"], "Bob")

    def test_peers_default_empty(self):
        msg = create_message("chat", "Alice", "hey")
        self.assertEqual(msg["peers"], [])

    def test_peers_populated(self):
        peers = ["127.0.0.1:5001", "127.0.0.1:5002"]
        msg = create_message("peer_list", "Alice", peers=peers)
        self.assertEqual(msg["peers"], peers)

    def test_timestamp_recent(self):
        before = time.time()
        msg = create_message("chat", "Alice", "now")
        after = time.time()
        self.assertGreaterEqual(msg["timestamp"], before)
        self.assertLessEqual(msg["timestamp"], after)

    def test_unique_ids(self):
        ids = {create_message("chat", "Alice", "x")["id"] for _ in range(100)}
        self.assertEqual(len(ids), 100)


if __name__ == "__main__":
    unittest.main()
