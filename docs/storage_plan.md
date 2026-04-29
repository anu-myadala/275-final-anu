# Recovery & Storage — Technical Research Plan

## Team Responsibilities

This team handles **persistence** and **recovery**:

- Persisting messages so they survive process restarts.
- Providing the message backlog to nodes that join the network late or
  return after an absence.

---

## Requirements

| Requirement | Details |
|---|---|
| Durability | Messages must survive application crashes. |
| Replay | A new or returning node receives recent history on join. |
| Deduplication | Replayed messages must not create duplicates. |
| Thread safety | The networking and UI threads both access the store. |
| Portability | No database server required; single-file DB. |

---

## Chosen Approach: SQLite

Python ships with `sqlite3` in the standard library.  SQLite provides:

- **Durability** via write-ahead logging (WAL).
- **Atomic transactions** preventing corrupt writes on crash.
- **`INSERT OR IGNORE`** for trivial deduplication by primary key.
- **In-memory mode** (`":memory:"`) for fast, isolated unit tests.

### Schema

```sql
CREATE TABLE messages (
    id        TEXT PRIMARY KEY,
    type      TEXT    NOT NULL,
    sender    TEXT    NOT NULL,
    timestamp REAL    NOT NULL,   -- Unix epoch with sub-second precision
    content   TEXT    NOT NULL,
    peers     TEXT    NOT NULL,   -- JSON array of "host:port" strings
    signature TEXT    NOT NULL
);

CREATE INDEX idx_timestamp ON messages (timestamp);
```

The `id` column is a UUIDv4 string generated at message creation time.
`INSERT OR IGNORE` on the primary key makes all writes idempotent.

---

## History Replay Protocol

When node **B** joins the network:

1. B sends a `history_request` message (unicast) to each bootstrap peer,
   containing B's own address as the `content` field.
2. Each bootstrap peer queries its `MessageStore.get_recent(limit=100)`
   and sends a `history_response` message back to B.
3. B receives the JSON array of messages, verifies each signature, and
   inserts them via `MessageStore.save()`.

Because `save()` uses `INSERT OR IGNORE`, messages B already has (from
gossip that arrived before the history response) are safely ignored.

### Sequence Diagram

```
  B                           A (bootstrap)
  │── history_request ──────▶ │
  │                           │  query last 100 chat msgs
  │◀── history_response ──── │
  │  INSERT OR IGNORE each    │
```

---

## Implementation

See [`p2p_chat/storage.py`](../p2p_chat/storage.py).

| Method | Purpose |
|---|---|
| `MessageStore(db_path)` | Opens / creates the database and schema. |
| `save(message)` | Persists a message; silently ignores duplicates. |
| `get_recent(limit)` | Returns up to *limit* chat messages, oldest first. |
| `count()` | Returns total row count (all message types). |

Pass `db_path=":memory:"` in tests to avoid touching the filesystem.

---

## Limitations & Future Work

| Limitation | Notes |
|---|---|
| Unbounded growth | The database grows indefinitely. A periodic vacuum / TTL eviction policy should be added. |
| No full-text search | SQLite FTS5 could power a `/search` command. |
| Single-node history source | Only one bootstrap peer is queried. Multiple peers could be queried and their responses merged for better coverage. |
| No snapshots | A daily snapshot file would speed up replay for very long histories. |

---

## Testing

Unit tests in [`tests/test_storage.py`](../tests/test_storage.py) cover:

- Save and retrieve a message.
- Duplicate saves are silently ignored.
- Only `"chat"` messages are returned by `get_recent`.
- Chronological ordering.
- `limit` parameter is respected.
- Field round-trip integrity.
