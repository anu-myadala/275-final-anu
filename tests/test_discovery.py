"""Unit tests for p2p_chat.discovery."""

import unittest

from p2p_chat.discovery import PeerRegistry


class TestPeerRegistry(unittest.TestCase):
    def test_add_peer(self):
        reg = PeerRegistry("127.0.0.1:5000")
        reg.add("127.0.0.1:5001")
        self.assertIn("127.0.0.1:5001", reg)

    def test_own_address_not_added(self):
        reg = PeerRegistry("127.0.0.1:5000")
        reg.add("127.0.0.1:5000")
        self.assertNotIn("127.0.0.1:5000", reg)

    def test_add_many(self):
        reg = PeerRegistry("127.0.0.1:5000")
        reg.add_many(["127.0.0.1:5001", "127.0.0.1:5002", "127.0.0.1:5003"])
        self.assertEqual(len(reg), 3)

    def test_add_many_excludes_self(self):
        reg = PeerRegistry("127.0.0.1:5000")
        reg.add_many(["127.0.0.1:5000", "127.0.0.1:5001"])
        self.assertEqual(len(reg), 1)

    def test_remove_peer(self):
        reg = PeerRegistry("127.0.0.1:5000")
        reg.add("127.0.0.1:5001")
        reg.remove("127.0.0.1:5001")
        self.assertNotIn("127.0.0.1:5001", reg)

    def test_remove_nonexistent_is_noop(self):
        reg = PeerRegistry("127.0.0.1:5000")
        # Should not raise.
        reg.remove("127.0.0.1:9999")

    def test_peers_returns_snapshot(self):
        reg = PeerRegistry("127.0.0.1:5000")
        reg.add("127.0.0.1:5001")
        reg.add("127.0.0.1:5002")
        peers = reg.peers()
        self.assertIsInstance(peers, list)
        self.assertEqual(set(peers), {"127.0.0.1:5001", "127.0.0.1:5002"})

    def test_no_duplicates(self):
        reg = PeerRegistry("127.0.0.1:5000")
        reg.add("127.0.0.1:5001")
        reg.add("127.0.0.1:5001")
        self.assertEqual(len(reg), 1)

    def test_empty_string_ignored(self):
        reg = PeerRegistry("127.0.0.1:5000")
        reg.add("")
        self.assertEqual(len(reg), 0)


if __name__ == "__main__":
    unittest.main()
