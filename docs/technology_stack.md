# Technology Stack — Technical Research Plan

## Team Responsibilities

This team evaluated available tools and libraries and made the key
technology decisions for the project.  All decisions were ratified by
the class.

---

## Core Decision: Python 3.12

The class unanimously agreed to build the entire application in
**Python 3.12**.

| Criterion | Python 3.12 |
|---|---|
| Team familiarity | High — everyone knows Python from coursework. |
| Standard library | Rich: `socket`, `threading`, `sqlite3`, `hmac`, `hashlib`, `curses`, `json`, `uuid`, `argparse` — all built in. |
| Cross-platform | Runs on Linux, macOS, Windows (WSL). |
| Readable code | Reduces onboarding time for contributors. |
| Performance | Sufficient for a class-scale prototype (< 50 nodes). |

---

## Standard Library Components

| Module | Used for |
|---|---|
| `socket` | TCP server/client sockets for peer communication. |
| `threading` | Background server thread, per-connection handler threads. |
| `sqlite3` | Message persistence (file-based or in-memory). |
| `hmac` + `hashlib` | HMAC-SHA256 message signing. |
| `curses` | Terminal UI (split-screen, real-time updates). |
| `json` | Message serialisation / deserialisation. |
| `uuid` | Unique message ID generation (UUIDv4). |
| `argparse` | Command-line interface. |
| `unittest` | Unit and integration tests. |

**Zero external dependencies** — the application installs with a plain
`git clone` and `python -m p2p_chat …`.

---

## Project Structure

```
275-final-anu/
├── p2p_chat/
│   ├── __init__.py
│   ├── security.py       # HMAC signing & verification
│   ├── storage.py        # SQLite message store
│   ├── discovery.py      # Peer registry
│   ├── node.py           # P2P networking & gossip
│   ├── ui.py             # curses terminal UI
│   └── main.py           # CLI entry point
├── tests/
│   ├── test_security.py
│   ├── test_storage.py
│   ├── test_discovery.py
│   └── test_node.py
├── docs/
│   ├── security_plan.md
│   ├── ui_plan.md
│   ├── discovery_plan.md
│   ├── storage_plan.md
│   └── technology_stack.md
└── README.md
```

---

## Development Workflow

| Tool | Purpose |
|---|---|
| **GitHub** (branching) | Each team works on a feature branch; PRs merge to `main`. |
| **Discord** | Coordination, Q&A, code review discussion. |
| `python -m pytest tests/` | Run the full test suite. |
| `python -m p2p_chat --help` | Verify the CLI. |

---

## Considered Alternatives

### asyncio instead of threading

`asyncio` would be more efficient at high concurrency but has a steeper
learning curve and makes the code harder to reason about for beginners.
`threading` is sufficient for a class-scale prototype.

### External databases (PostgreSQL, Redis)

Would require a running server process on every machine.  SQLite is
serverless and portable — no installation beyond Python.

### WebSocket / HTTP transport

Would add Flask or aiohttp as dependencies and require a browser or
separate client.  Raw TCP sockets keep the stack minimal.

### Asymmetric encryption (TLS / PKI)

Rejected by class vote — too complex to distribute keys.  HMAC with a
shared secret is the pragmatic choice for the prototype.

---

## Future Upgrades

| Area | Potential Technology |
|---|---|
| Per-user authentication | Ed25519 asymmetric key pairs (`cryptography` library). |
| NAT traversal | STUN/TURN (e.g. via `aiortc`). |
| Structured overlay | Kademlia DHT for scalable peer discovery. |
| Web UI | FastAPI + WebSocket backend + React frontend. |
| Packaging | `pyproject.toml` + `pip install p2p_chat`. |
