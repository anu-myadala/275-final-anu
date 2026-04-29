# 275-final-anu — P2P Distributed Chat

A **peer-to-peer terminal chat application** written entirely in Python 3 with
no external dependencies.  Each participant runs a node that connects directly
to other participants — there is no central server.

---

## Features

| Feature | Implementation |
|---|---|
| **Message integrity** | Every message is signed with HMAC-SHA256 so tampering is detected. |
| **Peer discovery** | Bootstrap peer + peer-list exchange; gossip propagation for new arrivals. |
| **Message history** | New/returning nodes request and replay the recent message backlog. |
| **Persistence** | All messages are stored in a local SQLite database. |
| **Terminal UI** | Split-screen curses interface: scrolling message pane + input line. |

---

## Quick Start

```bash
# No pip install needed — uses Python stdlib only.

# Clone the repo and enter it.
git clone <repo-url>
cd 275-final-anu

# Start the first node (no peers yet).
python -m p2p_chat --username Alice --port 5000

# In another terminal (or on another machine), join via Alice's node.
python -m p2p_chat --username Bob --port 5001 --bootstrap 127.0.0.1:5000

# A third participant.
python -m p2p_chat --username Charlie --port 5002 --bootstrap 127.0.0.1:5000
```

### In-app Commands

| Command | Effect |
|---|---|
| *(any text)* | Send a chat message to all peers. |
| `/peers` | List currently known peer addresses. |
| `/help` | Show command reference. |
| `/quit` | Broadcast a leave notice and exit. |

---

## CLI Reference

```
python -m p2p_chat [OPTIONS]

Options:
  --username TEXT     Your display name (required).
  --host TEXT         Bind address (default: 0.0.0.0).
  --port INT          TCP port to listen on (default: 5000).
  --bootstrap ADDR    Bootstrap peer as host:port (repeatable).
  --db PATH           SQLite database path (default: chat_log.db).
  --secret TEXT       Shared HMAC secret for the room.
```

---

## Running the Tests

```bash
python -m pytest tests/ -v
```

All tests use the Python standard library (`unittest`) and run without
any external services.

---

## Project Structure

```
p2p_chat/
├── __init__.py
├── security.py   — HMAC-SHA256 message signing & verification
├── storage.py    — SQLite-backed message persistence
├── discovery.py  — Thread-safe peer registry
├── node.py       — TCP server, gossip broadcast, deduplication
├── ui.py         — curses split-screen terminal UI
└── main.py       — argparse CLI entry point

tests/
├── test_security.py
├── test_storage.py
├── test_discovery.py
└── test_node.py

docs/
├── security_plan.md       — Security team research document
├── ui_plan.md             — UI team research document
├── discovery_plan.md      — Discovery team research document
├── storage_plan.md        — Storage team research document
└── technology_stack.md    — Tech-stack team research document
```

---

## Architecture Overview

```
  ┌──────────┐   TCP (JSON/newline)   ┌──────────┐
  │  Node A  │ ─────────────────────▶ │  Node B  │
  │  Alice   │ ◀───────────────────── │  Bob     │
  └──────────┘                        └──────────┘
       │  gossip                           │
       ▼                                   ▼
  ┌──────────┐                        ┌──────────┐
  │  Node C  │                        │  Node D  │
  │  Charlie │                        │  Dave    │
  └──────────┘                        └──────────┘
```

Each node:
1. Runs a TCP server on its listen port.
2. Accepts short-lived inbound connections (one message per connection).
3. Verifies the HMAC signature of every received message.
4. Deduplicates via a seen-ID set (prevents gossip loops).
5. Stores `"chat"` messages in SQLite.
6. Forwards the message to all known peers (gossip).

---

## Team & Coordination

- **Discord**: team coordination channel.
- **GitHub**: feature branches + pull requests into `main`.
- Each sub-team uploads a research document to `docs/` before the deadline.