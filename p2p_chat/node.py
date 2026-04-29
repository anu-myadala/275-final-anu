"""Networking core: P2P node with gossip-style message distribution.

Each node:

1. Runs a TCP server that accepts incoming single-message connections.
2. Keeps a :class:`~p2p_chat.discovery.PeerRegistry` of known peers.
3. When it receives a new message it stores it, updates the UI, then
   *gossips* it to every peer it knows about (deduplication via a
   seen-ID set prevents infinite loops).
4. On start-up it broadcasts a ``"join"`` message and requests the
   message history from each bootstrap peer.
5. On shut-down it broadcasts a ``"leave"`` message.

Protocol
--------
All messages are newline-terminated JSON objects sent over a fresh TCP
connection.  The sender connects, writes ``<json>\\n``, then closes the
socket.  This *connect-send-close* model keeps the implementation
simple: no connection management, no keep-alive, no framing.
"""

import json
import socket
import threading
from typing import Callable

from .discovery import PeerRegistry
from .security import create_message, verify_message
from .storage import MessageStore

# Timeout in seconds for outbound connections.
_CONNECT_TIMEOUT = 3

# Maximum simultaneous inbound handler threads.
_SERVER_BACKLOG = 20

# Number of recent messages to replay to a newly joined peer.
_HISTORY_REPLAY_LIMIT = 100


class Node:
    """A single participant in the P2P chat network.

    Parameters
    ----------
    host:
        IP address to bind the server socket to (e.g. ``"0.0.0.0"``).
    port:
        TCP port for the server socket.
    username:
        Display name shown next to outgoing messages.
    store:
        :class:`~p2p_chat.storage.MessageStore` instance used for
        persistence and history replay.
    registry:
        :class:`~p2p_chat.discovery.PeerRegistry` instance.
    on_message:
        Callback invoked on the networking thread whenever a new
        ``"chat"`` message arrives (including ones sent by this node).
        Signature: ``on_message(msg: dict) -> None``.
    secret:
        HMAC secret shared by all nodes in the network.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        store: MessageStore,
        registry: PeerRegistry,
        on_message: Callable[[dict], None],
        secret: bytes = b"p2p-chat-shared-secret-2024",
    ) -> None:
        self.host = host
        self.port = port
        self.address = f"{host}:{port}"
        self.username = username
        self._store = store
        self._registry = registry
        self._on_message = on_message
        self._secret = secret

        self._seen_ids: set[str] = set()
        self._seen_lock = threading.Lock()
        self._server_sock: socket.socket | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Life-cycle
    # ------------------------------------------------------------------

    def start(self, bootstrap_peers: list[str] | None = None) -> None:
        """Start the server thread and join the network."""
        self._running = True
        t = threading.Thread(target=self._server_loop, daemon=True, name="p2p-server")
        t.start()

        if bootstrap_peers:
            for addr in bootstrap_peers:
                self._registry.add(addr)
            # Announce ourselves and request history from each bootstrap peer.
            join_msg = create_message(
                "join",
                self.username,
                content=self.address,
                secret=self._secret,
            )
            self._mark_seen(join_msg["id"])
            for addr in bootstrap_peers:
                self._send_to(addr, join_msg)
            self._request_history(bootstrap_peers)

    def stop(self) -> None:
        """Broadcast a leave message and shut down the server."""
        self._running = False
        leave_msg = create_message(
            "leave",
            self.username,
            content=self.address,
            secret=self._secret,
        )
        self._mark_seen(leave_msg["id"])
        self._gossip(leave_msg)
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Public send
    # ------------------------------------------------------------------

    def send_chat(self, content: str) -> None:
        """Create, store, display and broadcast a chat message."""
        msg = create_message("chat", self.username, content=content, secret=self._secret)
        self._mark_seen(msg["id"])
        self._store.save(msg)
        self._on_message(msg)
        self._gossip(msg)

    # ------------------------------------------------------------------
    # Server
    # ------------------------------------------------------------------

    def _server_loop(self) -> None:
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._server_sock.bind((self.host, self.port))
        except OSError as exc:
            raise RuntimeError(
                f"Cannot bind to {self.host}:{self.port} — {exc}"
            ) from exc
        self._server_sock.listen(_SERVER_BACKLOG)

        while self._running:
            try:
                conn, _ = self._server_sock.accept()
                threading.Thread(
                    target=self._handle_conn,
                    args=(conn,),
                    daemon=True,
                ).start()
            except OSError:
                break

    def _handle_conn(self, conn: socket.socket) -> None:
        try:
            data = b""
            conn.settimeout(5)
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                data += chunk
                # Messages are newline-delimited; process each complete one.
                while b"\n" in data:
                    line, data = data.split(b"\n", 1)
                    if line.strip():
                        try:
                            msg = json.loads(line.decode())
                            self._dispatch(msg)
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            pass
        except (OSError, socket.timeout):
            pass
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Message dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, msg: dict) -> None:
        if not verify_message(msg, self._secret):
            return  # Drop tampered / unknown messages.

        msg_id = msg.get("id", "")
        if not msg_id or not self._mark_seen(msg_id):
            return  # Already processed.

        msg_type = msg.get("type")

        if msg_type == "chat":
            self._store.save(msg)
            self._on_message(msg)
            self._gossip(msg)

        elif msg_type == "join":
            peer_addr = msg.get("content", "")
            if peer_addr:
                self._registry.add(peer_addr)
            # Share our current peer list with the new arrival.
            peer_list_msg = create_message(
                "peer_list",
                self.username,
                peers=[self.address] + self._registry.peers(),
                secret=self._secret,
            )
            self._mark_seen(peer_list_msg["id"])
            if peer_addr:
                self._send_to(peer_addr, peer_list_msg)
            self._gossip(msg)

        elif msg_type == "leave":
            peer_addr = msg.get("content", "")
            if peer_addr:
                self._registry.remove(peer_addr)
            self._gossip(msg)

        elif msg_type == "peer_list":
            self._registry.add_many(msg.get("peers", []))

        elif msg_type == "history_request":
            requester = msg.get("content", "")
            if requester:
                self._send_history(requester)

        elif msg_type == "history_response":
            self._apply_history(msg)

    # ------------------------------------------------------------------
    # History (recovery)
    # ------------------------------------------------------------------

    def _request_history(self, peers: list[str]) -> None:
        req = create_message(
            "history_request",
            self.username,
            content=self.address,
            secret=self._secret,
        )
        self._mark_seen(req["id"])
        for addr in peers:
            self._send_to(addr, req)

    def _send_history(self, requester: str) -> None:
        recent = self._store.get_recent(_HISTORY_REPLAY_LIMIT)
        resp = create_message(
            "history_response",
            self.username,
            content=json.dumps(recent),
            secret=self._secret,
        )
        self._mark_seen(resp["id"])
        self._send_to(requester, resp)

    def _apply_history(self, msg: dict) -> None:
        try:
            messages = json.loads(msg.get("content", "[]"))
        except (json.JSONDecodeError, TypeError):
            return
        for m in messages:
            m_id = m.get("id", "")
            if m_id and self._mark_seen(m_id) and verify_message(m, self._secret):
                if m.get("type") == "chat":
                    self._store.save(m)

    # ------------------------------------------------------------------
    # Gossip / transport
    # ------------------------------------------------------------------

    def _gossip(self, msg: dict) -> None:
        """Forward *msg* to every known peer."""
        for addr in self._registry.peers():
            self._send_to(addr, msg)

    def _send_to(self, address: str, msg: dict) -> None:
        """Open a short-lived TCP connection and send *msg* as JSON."""
        try:
            host, port_str = address.rsplit(":", 1)
            port = int(port_str)
        except ValueError:
            return
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(_CONNECT_TIMEOUT)
                s.connect((host, port))
                s.sendall(json.dumps(msg).encode() + b"\n")
        except OSError:
            # Mark the peer as unreachable so we stop forwarding to it.
            self._registry.remove(address)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _mark_seen(self, msg_id: str) -> bool:
        """Mark *msg_id* as seen.  Returns ``True`` if it was *not* seen
        before (i.e. the caller should process it)."""
        with self._seen_lock:
            if msg_id in self._seen_ids:
                return False
            self._seen_ids.add(msg_id)
            return True
