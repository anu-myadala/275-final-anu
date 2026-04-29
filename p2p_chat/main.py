"""Entry point for the p2p_chat application.

Usage
-----
Start the first node (no bootstrap peers)::

    python -m p2p_chat --username Alice --port 5000

Join an existing network via a bootstrap peer::

    python -m p2p_chat --username Bob --port 5001 --bootstrap 127.0.0.1:5000

Options
-------
--username TEXT     Your display name (required).
--host TEXT         Bind address for the server socket (default: 0.0.0.0).
--port INT          TCP port to listen on (default: 5000).
--bootstrap ADDR    host:port of a peer already in the network (repeatable).
--db PATH           Path to the SQLite database file (default: chat_log.db).
--secret TEXT       Shared HMAC secret for all nodes in the same room
                    (default: built-in development secret).
"""

import argparse
import sys

from .discovery import PeerRegistry
from .node import Node
from .security import DEFAULT_SECRET
from .storage import MessageStore
from .ui import ChatUI


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="p2p_chat",
        description="Peer-to-peer distributed terminal chat.",
    )
    parser.add_argument("--username", required=True, help="Your display name.")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address.")
    parser.add_argument("--port", type=int, default=5000, help="Listen port.")
    parser.add_argument(
        "--bootstrap",
        action="append",
        dest="bootstrap",
        metavar="HOST:PORT",
        default=[],
        help="Bootstrap peer address (may be repeated).",
    )
    parser.add_argument("--db", default="chat_log.db", help="SQLite database path.")
    parser.add_argument(
        "--secret",
        default=None,
        help="Shared HMAC secret (ASCII).  Defaults to built-in dev secret.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    secret: bytes = (
        args.secret.encode() if args.secret else DEFAULT_SECRET
    )

    store = MessageStore(db_path=args.db)
    own_address = f"{args.host}:{args.port}"
    # Use the loopback address in the registry key when binding to 0.0.0.0
    # so outbound connections work correctly on the local machine.
    announce_address = (
        f"127.0.0.1:{args.port}" if args.host == "0.0.0.0" else own_address
    )
    registry = PeerRegistry(own_address=announce_address)

    # Load historical messages so they are visible before any network activity.
    backlog = store.get_recent(limit=200)

    def on_quit() -> None:
        node.stop()

    # The UI is created first so we have the callback ready.
    ui = ChatUI(
        username=args.username,
        on_send=lambda text: node.send_chat(text),
        on_quit=on_quit,
        get_peers=registry.peers,
    )

    node = Node(
        host=args.host,
        port=args.port,
        username=args.username,
        store=store,
        registry=registry,
        on_message=ui.add_message,
        secret=secret,
    )

    node.start(bootstrap_peers=args.bootstrap or None)

    # Replay stored messages into the UI so returning users see history.
    for msg in backlog:
        ui.add_message(msg)

    ui.system_message(
        f"Connected as {args.username} on port {args.port}.  "
        "Type /help for commands."
    )

    # Blocks until the user types /quit.
    ui.run()


if __name__ == "__main__":
    main()
