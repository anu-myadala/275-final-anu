# Security & Signatures — Technical Research Plan

## Team Responsibilities

This team is responsible for ensuring that all messages exchanged over the
peer-to-peer network are **tamper-evident**: any modification to a message in
transit must be detectable by the receiving node.

---

## Problem Statement

In a decentralised network there is no trusted central authority to validate
messages.  A malicious node (or a man-in-the-middle attacker) could:

- Alter the text of a message after it is sent.
- Replay old messages with a forged timestamp.
- Inject messages that appear to come from another user.

We need a lightweight mechanism that all nodes can use to independently verify
that a received message has not been changed since the legitimate sender
created it.

---

## Chosen Approach: HMAC-SHA256

### Why HMAC?

The class decided to **skip asymmetric (PKI) encryption** because key
distribution at scale is complex.  Instead we use a **symmetric MAC**:

| Property | HMAC-SHA256 |
|---|---|
| Algorithm | HMAC constructed over SHA-256 |
| Key type | Shared secret (bytes) |
| Output size | 32 bytes (64 hex chars) |
| Collision resistance | 2^128 effective security |
| Python support | `hmac` + `hashlib` — stdlib, no extra dependencies |

A shared secret (pre-agreed by all participants in a "room") is used as the
HMAC key.  Every node uses the same secret, so every node can both *create*
and *verify* signatures.

### Message Format

Each message is a JSON object with the following fields:

```json
{
  "id":        "<UUIDv4>",
  "type":      "chat | join | leave | peer_list | history_request | history_response",
  "sender":    "<username>",
  "timestamp": 1714000000.123,
  "content":   "<text or serialised payload>",
  "peers":     ["host:port", "..."],
  "signature": "<64-char hex HMAC-SHA256>"
}
```

### Signing Algorithm

1. Take all fields **except** `"signature"`.
2. Serialise to JSON with **sorted keys** and no extra whitespace
   (deterministic canonical form).
3. Compute `HMAC-SHA256(canonical_json, shared_secret)`.
4. Attach the hex digest as `"signature"`.

### Verification Algorithm

1. Extract `"signature"` from the received message.
2. Re-compute the expected signature using the same canonical form.
3. Use `hmac.compare_digest()` (constant-time comparison) to prevent
   **timing attacks**.
4. Accept the message only if the digests match.

---

## Implementation

See [`p2p_chat/security.py`](../p2p_chat/security.py).

Key functions:

| Function | Purpose |
|---|---|
| `sign_message(msg, secret)` | Returns the hex HMAC digest |
| `verify_message(msg, secret)` | Returns `True` iff the signature is valid |
| `create_message(type, sender, …)` | Builds a fully-signed message dict |

---

## Limitations & Future Work

| Limitation | Notes |
|---|---|
| No replay protection | A captured message with a valid signature can be re-sent. Mitigation: add a short TTL and track seen message IDs (already done via the dedup set in `node.py`). |
| Shared secret distribution | All nodes must agree on the secret out-of-band. A future version could use a Diffie-Hellman key exchange per session. |
| No sender authentication | Any node that knows the secret can forge a message from any sender name. A future upgrade would use per-user asymmetric key pairs. |

---

## Testing

Unit tests live in [`tests/test_security.py`](../tests/test_security.py) and
cover:

- Valid signatures pass verification.
- Modified content/sender fails verification.
- Wrong secret fails verification.
- `create_message` produces unique IDs and recent timestamps.
