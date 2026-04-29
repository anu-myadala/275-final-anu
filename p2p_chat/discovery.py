"""Discovery module: peer registry and address propagation.

When a node starts it contacts one or more *bootstrap* peers and
exchanges peer lists.  Thereafter every ``"join"`` and ``"peer_list"``
message enriches the local registry so each node maintains a
reasonably up-to-date view of the current participants.
"""

import threading


class PeerRegistry:
    """Thread-safe set of known peer addresses.

    An *address* is a ``"host:port"`` string, e.g. ``"127.0.0.1:5001"``.

    Parameters
    ----------
    own_address:
        The address of *this* node — it will never be added to the
        registry so the node does not try to connect to itself.
    """

    def __init__(self, own_address: str) -> None:
        self.own_address = own_address
        self._peers: set[str] = set()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, address: str) -> None:
        """Register *address* unless it is our own address."""
        if address and address != self.own_address:
            with self._lock:
                self._peers.add(address)

    def add_many(self, addresses: list[str]) -> None:
        """Register every address in *addresses*."""
        for addr in addresses:
            self.add(addr)

    def remove(self, address: str) -> None:
        """Unregister *address* (e.g. when a connection fails)."""
        with self._lock:
            self._peers.discard(address)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def peers(self) -> list[str]:
        """Return a snapshot of the current peer list."""
        with self._lock:
            return list(self._peers)

    def __len__(self) -> int:
        with self._lock:
            return len(self._peers)

    def __contains__(self, address: str) -> bool:
        with self._lock:
            return address in self._peers
