"""Integration tests for p2p_chat.node.

These tests spin up real Node instances on loopback ports and verify
end-to-end behaviour: message delivery, gossip, peer discovery, and
history replay.
"""

import json
import socket as _socket_module
import threading
import time
import unittest

from p2p_chat.discovery import PeerRegistry
from p2p_chat.node import Node
from p2p_chat.security import DEFAULT_SECRET, create_message, verify_message
from p2p_chat.storage import MessageStore

# Global lock + counter to hand out unique port pairs across all tests.
_port_lock = threading.Lock()
_next_port = 15300


def _alloc_port() -> int:
    """Return an unused loopback port."""
    with _socket_module.socket(_socket_module.AF_INET, _socket_module.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _make_node(port: int, username: str) -> tuple[Node, list[dict]]:
    """Create a Node bound to *port* and return it with a received-messages list."""
    store = MessageStore(":memory:")
    registry = PeerRegistry(f"127.0.0.1:{port}")
    received: list[dict] = []

    node = Node(
        host="127.0.0.1",
        port=port,
        username=username,
        store=store,
        registry=registry,
        on_message=lambda msg: received.append(msg),
        secret=DEFAULT_SECRET,
    )
    return node, received


def _wait(condition, timeout: float = 3.0, interval: float = 0.05) -> bool:
    """Poll *condition* until it returns True or *timeout* expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(interval)
    return False


class TestNodeMessaging(unittest.TestCase):
    """Two-node tests: Alice sends, Bob receives."""

    def setUp(self):
        self.port_a = _alloc_port()
        self.port_b = _alloc_port()
        self.node_a, self.recv_a = _make_node(self.port_a, "Alice")
        self.node_b, self.recv_b = _make_node(self.port_b, "Bob")
        self.node_a.start()
        self.node_b.start(bootstrap_peers=[f"127.0.0.1:{self.port_a}"])
        # Give the join handshake time to complete.
        time.sleep(0.3)

    def tearDown(self):
        self.node_a.stop()
        self.node_b.stop()
        time.sleep(0.1)

    def test_chat_delivered_to_peer(self):
        self.node_a.send_chat("Hello Bob!")
        self.assertTrue(
            _wait(lambda: any(m["content"] == "Hello Bob!" for m in self.recv_b)),
            "Bob did not receive Alice's message within timeout.",
        )

    def test_chat_shown_locally(self):
        self.node_a.send_chat("local echo")
        self.assertTrue(
            _wait(lambda: any(m["content"] == "local echo" for m in self.recv_a)),
            "Alice's own message was not echoed locally.",
        )

    def test_message_signature_valid(self):
        self.node_a.send_chat("signed message")
        _wait(lambda: any(m["content"] == "signed message" for m in self.recv_b))
        delivered = next(m for m in self.recv_b if m["content"] == "signed message")
        self.assertTrue(verify_message(delivered))

    def test_no_duplicates(self):
        self.node_a.send_chat("unique msg")
        _wait(lambda: len([m for m in self.recv_b if m["content"] == "unique msg"]) >= 1)
        time.sleep(0.3)
        count = sum(1 for m in self.recv_b if m["content"] == "unique msg")
        self.assertEqual(count, 1, "Message was delivered more than once.")


class TestNodeHistory(unittest.TestCase):
    """History replay: new node receives backlog."""

    def test_history_replayed_to_new_peer(self):
        port_a = _alloc_port()
        port_b = _alloc_port()
        node_a, recv_a = _make_node(port_a, "Alice")
        node_a.start()

        # Alice sends several messages before Bob joins.
        for i in range(3):
            node_a.send_chat(f"pre-join message {i}")
        time.sleep(0.2)

        node_b, recv_b = _make_node(port_b, "Bob")
        node_b.start(bootstrap_peers=[f"127.0.0.1:{port_a}"])

        # Bob's store should eventually contain Alice's pre-join messages.
        self.assertTrue(
            _wait(lambda: node_b._store.count() >= 3),
            "Bob did not receive the pre-join history.",
        )

        node_a.stop()
        node_b.stop()
        time.sleep(0.1)


class TestNodeTamperedMessage(unittest.TestCase):
    """Tampered messages must be silently dropped."""

    def test_tampered_message_dropped(self):
        port_a = _alloc_port()
        port_b = _alloc_port()
        node_a, recv_a = _make_node(port_a, "Alice")
        node_b, recv_b = _make_node(port_b, "Bob")
        node_a.start()
        node_b.start(bootstrap_peers=[f"127.0.0.1:{port_a}"])
        time.sleep(0.3)

        # Manually craft a tampered message and send it directly to node_b.
        evil = create_message("chat", "Mallory", "tampered")
        evil["content"] = "I am not Mallory"  # invalidates signature

        with _socket_module.socket(_socket_module.AF_INET, _socket_module.SOCK_STREAM) as s:
            s.connect(("127.0.0.1", port_b))
            s.sendall(json.dumps(evil).encode() + b"\n")

        time.sleep(0.2)
        self.assertFalse(
            any(m["content"] == "I am not Mallory" for m in recv_b),
            "Tampered message was accepted — signature check failed.",
        )

        node_a.stop()
        node_b.stop()
        time.sleep(0.1)


if __name__ == "__main__":
    unittest.main()
