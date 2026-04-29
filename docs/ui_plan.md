# User Interface (UI) — Technical Research Plan

## Team Responsibilities

This team owns the visual presentation of the chat application: how
messages are displayed, how the user types and submits text, and how
system events (joins, leaves, errors) are communicated.

---

## Design Goals

| Goal | Rationale |
|---|---|
| No external GUI framework | Keeps the dependency footprint minimal; terminal works everywhere. |
| Real-time updates | Incoming messages must appear immediately without disrupting the user's typing. |
| Keyboard-driven | Target audience is developers comfortable with terminal tools. |
| Accessible | Works over SSH; no graphics card required. |

---

## Chosen Approach: Python `curses`

Python's standard library includes `curses`, a binding to the UNIX
ncurses terminal control library.  It allows us to:

- Divide the terminal window into **sub-windows** (panes).
- Update individual panes independently without redrawing the entire screen.
- Handle resize events (`KEY_RESIZE`) gracefully.
- Support colour highlights for usernames and system messages.

### Screen Layout

```
┌────────────────────────────────────────────────┐
│ [08:31:12] Alice: Hello everyone!              │  ← messages pane
│ [08:31:15] Bob:   Hey!                         │    (scrolling, read-only)
│ [08:31:20] ★: New peer joined: 127.0.0.1:5002  │
│                                                │
├────────────────────────────────────────────────┤  ← separator (─ × width)
│ Alice>  _                                      │  ← input pane
└────────────────────────────────────────────────┘
```

### Threading Model

The `curses` event loop runs on the **main thread**.  The input pane
uses a 500 ms timeout on `get_wch()` so the loop can periodically check
a `threading.Event` flag set by network callbacks.  When the flag is
set the messages pane is refreshed from the latest in-memory list.

This avoids calling curses functions from multiple threads (which is
unsafe) while still delivering sub-second latency for incoming messages.

---

## Commands

| Command | Action |
|---|---|
| `/quit` | Broadcast a leave message and exit. |
| `/peers` | List currently known peer addresses. |
| `/help` | Show the command reference. |
| *(plain text)* | Send a chat message to all peers. |

---

## Colour Scheme

| Element | Colour |
|---|---|
| Username prompt | Cyan + bold |
| System / info messages | Yellow |
| Separator line | White |
| Normal chat text | Terminal default |

---

## Implementation

See [`p2p_chat/ui.py`](../p2p_chat/ui.py).

Key class: `ChatUI`

| Method | Purpose |
|---|---|
| `add_message(msg)` | Thread-safe; appends to display list and sets dirty flag. |
| `system_message(text)` | Displays a synthetic info line not stored in the log. |
| `run()` | Blocks until the user quits; must be called from the main thread. |

---

## Limitations & Future Work

| Limitation | Notes |
|---|---|
| Terminal only | A web UI (e.g. FastAPI + WebSocket + React) would improve accessibility. |
| No message history scroll | The pane shows only the last *N* lines. Arrow-key scrolling could be added. |
| No username colours | Each sender could be assigned a distinct colour for readability. |
| No emoji support | Wide characters can confuse curses column counting; requires special handling. |
