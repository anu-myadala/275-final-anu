"""Security module: HMAC-SHA256 message signing and verification.

Every message that travels across the network carries a ``signature``
field that is an HMAC-SHA256 digest of the message's canonical JSON
representation (fields sorted alphabetically, signature field excluded).
This guarantees *integrity* — any in-transit modification of the
payload will cause signature verification to fail.

The shared secret is intentionally simple for the prototype.  A real
deployment would negotiate a per-channel secret out-of-band.
"""

import hashlib
import hmac
import json
import time
import uuid

# Default shared secret used by all nodes in the same "room".
# Override via the SHARED_SECRET argument when creating messages if needed.
DEFAULT_SECRET = b"p2p-chat-shared-secret-2024"


def _canonical(message: dict) -> bytes:
    """Return a deterministic bytes representation of *message* without
    the ``signature`` field so the same payload always produces the same
    digest regardless of field insertion order."""
    payload = {k: v for k, v in message.items() if k != "signature"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def sign_message(message: dict, secret: bytes = DEFAULT_SECRET) -> str:
    """Return the hex-encoded HMAC-SHA256 signature for *message*."""
    return hmac.new(secret, _canonical(message), hashlib.sha256).hexdigest()


def verify_message(message: dict, secret: bytes = DEFAULT_SECRET) -> bool:
    """Return ``True`` iff *message* carries a valid HMAC-SHA256 signature.

    Uses :func:`hmac.compare_digest` to prevent timing attacks.
    """
    if "signature" not in message:
        return False
    expected = sign_message(message, secret)
    return hmac.compare_digest(expected, message["signature"])


def create_message(
    msg_type: str,
    sender: str,
    content: str = "",
    peers: list | None = None,
    secret: bytes = DEFAULT_SECRET,
) -> dict:
    """Build a fully-signed message ready to be sent over the network.

    Parameters
    ----------
    msg_type:
        One of ``"chat"``, ``"join"``, ``"leave"``, ``"peer_list"``,
        ``"history_request"``, or ``"history_response"``.
    sender:
        Username of the originating node.
    content:
        Human-readable text (for ``"chat"`` messages) or serialised data
        (for ``"history_response"``).
    peers:
        List of ``"host:port"`` strings included in ``"peer_list"``
        messages.
    secret:
        HMAC secret; defaults to :data:`DEFAULT_SECRET`.
    """
    msg: dict = {
        "id": str(uuid.uuid4()),
        "type": msg_type,
        "sender": sender,
        "timestamp": time.time(),
        "content": content,
        "peers": peers or [],
    }
    msg["signature"] = sign_message(msg, secret)
    return msg
