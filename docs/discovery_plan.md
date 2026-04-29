# Discovery & Message Distribution — Technical Research Plan

## Team Responsibilities

This team solves two related problems:

1. **Discovery** — how does a new node find out who is already in the
   network?
2. **Distribution** — how does a message sent by one node reach *every*
   other node?

---

## Discovery: Bootstrap + Peer Exchange

### Bootstrap Peers

Every node is started with an optional list of `--bootstrap HOST:PORT`
addresses.  These are nodes that are *known to be online* (e.g. a
classmate's laptop on the same Wi-Fi, or a VPS with a static IP).  The
new node connects to each bootstrap peer and sends a `"join"` message
containing its own listen address.

### Peer Exchange

When a node receives a `"join"` message it replies with a `"peer_list"`
message containing all addresses it currently knows about (including
itself).  The new arrival adds all of these to its local `PeerRegistry`.

Every `"join"` message is also **gossiped** to existing peers so they
too learn about the newcomer.

### PeerRegistry

`PeerRegistry` is a thread-safe set of `"host:port"` strings.

```
new node  →  join(my_address)  →  bootstrap peer
             ←  peer_list([addr1, addr2, …])
new node adds all addresses to its registry
existing peers receive the gossiped join and add the new address
```

---

## Distribution: Gossip (Epidemic) Protocol

### Algorithm

When a node has a new message to broadcast (either one it originated
or one it received and has not yet forwarded):

1. Check the **seen-ID set**: if the message ID is already present, drop it.
2. Add the ID to the seen-ID set.
3. Process the message locally (store, display).
4. **Forward** the message to every address in the `PeerRegistry`.

This is a **push-based gossip** (also called *flooding*): every node
acts as a relay.  The seen-ID deduplication set prevents infinite loops.

### Message Types

| Type | Direction | Purpose |
|---|---|---|
| `chat` | broadcast | User-visible text message. |
| `join` | broadcast | Announces a new peer's address. |
| `leave` | broadcast | Announces a departing peer's address. |
| `peer_list` | unicast (reply) | Shares known peer addresses with a new arrival. |
| `history_request` | unicast | Asks a peer to send its recent message log. |
| `history_response` | unicast | Delivers the log to the requesting node. |

### Transport

Each message is sent over a **short-lived TCP connection**
(connect → send JSON line → close).  TCP provides ordered, reliable
delivery per connection; the gossip layer provides reachability in a
partially-connected graph.

---

## Scalability Considerations

| Scenario | Behaviour |
|---|---|
| Small network (< 20 nodes) | Full flooding is acceptable; every node gets every message. |
| Failed peer | `_send_to` catches `OSError` and calls `registry.remove()`. The dead address is pruned automatically. |
| Network partition | Messages sent before the partition are not delivered across it. After reconnection new messages propagate; the history-replay mechanism recovers missed messages. |
| Large network | Full flooding creates O(n²) messages. A future improvement would be a structured overlay (e.g. Chord DHT or a gossip fanout limit). |

---

## Implementation

| File | Key class/function |
|---|---|
| [`p2p_chat/discovery.py`](../p2p_chat/discovery.py) | `PeerRegistry` |
| [`p2p_chat/node.py`](../p2p_chat/node.py) | `Node._gossip`, `Node._dispatch` |

---

## Testing

Integration tests in [`tests/test_node.py`](../tests/test_node.py) cover:

- A message sent by node A is delivered to node B.
- No duplicate deliveries.
- Peer-list exchange after join.
