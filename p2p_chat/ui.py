"""Terminal user interface using Python's built-in curses library.

The screen is split into three panes:

  ┌────────────────────────────────────────┐
  │  messages  (scrolling, read-only)      │
  ├────────────────────────────────────────┤  ← separator
  │  username>  [input line]               │
  └────────────────────────────────────────┘

Incoming messages posted from the networking thread call
:meth:`ChatUI.add_message` which safely refreshes the message pane
from any thread via a threading.Event / redraw flag.

Commands
--------
``/quit``  — leave the network and exit.
``/peers`` — list currently known peers.
``/help``  — show available commands.
"""

import curses
import datetime
import threading
from typing import Callable


def _fmt_time(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")


class ChatUI:
    """curses-based split-screen chat interface.

    Parameters
    ----------
    username:
        Displayed as the prompt prefix.
    on_send:
        Callback invoked (in the UI thread) with the text the user
        submitted.  Signature: ``on_send(text: str) -> None``.
    on_quit:
        Called when the user types ``/quit``.
    get_peers:
        Callable that returns the current list of peer addresses.
    """

    def __init__(
        self,
        username: str,
        on_send: Callable[[str], None],
        on_quit: Callable[[], None],
        get_peers: Callable[[], list[str]],
    ) -> None:
        self.username = username
        self._on_send = on_send
        self._on_quit = on_quit
        self._get_peers = get_peers

        self._messages: list[dict] = []
        self._msg_lock = threading.Lock()
        self._dirty = threading.Event()

        self._msg_win: curses.window | None = None
        self._input_win: curses.window | None = None
        self._sep_win: curses.window | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Thread-safe public API
    # ------------------------------------------------------------------

    def add_message(self, msg: dict) -> None:
        """Append *msg* to the display list and schedule a redraw."""
        with self._msg_lock:
            self._messages.append(msg)
        self._dirty.set()

    def system_message(self, text: str) -> None:
        """Display an informational line (not stored in the log)."""
        fake = {
            "id": "",
            "type": "system",
            "sender": "★",
            "timestamp": __import__("time").time(),
            "content": text,
            "peers": [],
            "signature": "",
        }
        self.add_message(fake)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Block until the user quits.  Must be called from the main thread."""
        self._running = True
        curses.wrapper(self._main)

    # ------------------------------------------------------------------
    # curses internals
    # ------------------------------------------------------------------

    def _main(self, stdscr: curses.window) -> None:
        self._stdscr = stdscr
        curses.curs_set(1)
        curses.start_color()
        curses.use_default_colors()
        # Colour pairs: 1 = username bold, 2 = system/star, 3 = separator
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_YELLOW, -1)
        curses.init_pair(3, curses.COLOR_WHITE, -1)

        self._layout(stdscr)
        self._refresh_messages()
        self._input_loop()

    def _layout(self, stdscr: curses.window) -> None:
        """Create / recreate the sub-windows."""
        h, w = stdscr.getmaxyx()
        msg_h = max(h - 3, 1)

        self._msg_win = curses.newwin(msg_h, w, 0, 0)
        self._msg_win.scrollok(True)

        self._sep_win = curses.newwin(1, w, msg_h, 0)
        try:
            self._sep_win.addstr(0, 0, "─" * (w - 1), curses.color_pair(3))
        except curses.error:
            pass
        self._sep_win.refresh()

        self._input_win = curses.newwin(2, w, msg_h + 1, 0)

    def _refresh_messages(self) -> None:
        win = self._msg_win
        if win is None:
            return
        with self._msg_lock:
            msgs = list(self._messages)
        h, w = win.getmaxyx()
        win.erase()
        visible = msgs[-(h):]
        for row, msg in enumerate(visible):
            if row >= h:
                break
            ts = _fmt_time(msg["timestamp"])
            sender = msg["sender"]
            content = msg["content"]
            line = f"[{ts}] {sender}: {content}"
            try:
                pair = curses.color_pair(2) if msg["type"] == "system" else 0
                win.addnstr(row, 0, line, w - 1, pair)
            except curses.error:
                pass
        win.refresh()

    def _draw_prompt(self, buf: str) -> None:
        win = self._input_win
        if win is None:
            return
        _, w = win.getmaxyx()
        win.erase()
        prompt = f"{self.username}> "
        try:
            win.addstr(0, 0, prompt, curses.color_pair(1) | curses.A_BOLD)
            win.addnstr(0, len(prompt), buf, w - len(prompt) - 1)
        except curses.error:
            pass
        win.refresh()

    def _input_loop(self) -> None:
        self._draw_prompt("")
        buf = ""

        while self._running:
            # Non-blocking check for new messages from other threads.
            if self._dirty.is_set():
                self._dirty.clear()
                self._refresh_messages()
                self._draw_prompt(buf)

            # Check for key input (half-second timeout so we can poll _dirty).
            if self._input_win is None:
                break
            self._input_win.timeout(500)
            try:
                ch = self._input_win.get_wch()
            except curses.error:
                continue  # timeout — loop back to poll dirty flag

            if ch == curses.KEY_RESIZE:
                h, w = self._stdscr.getmaxyx()
                self._stdscr.clear()
                self._stdscr.refresh()
                self._layout(self._stdscr)
                self._refresh_messages()
                self._draw_prompt(buf)
                continue

            if ch in ("\n", "\r", curses.KEY_ENTER):
                text = buf.strip()
                buf = ""
                if text:
                    self._handle_input(text)
                self._draw_prompt(buf)

            elif ch in (curses.KEY_BACKSPACE, "\x7f", "\b", 127):
                buf = buf[:-1]
                self._draw_prompt(buf)

            elif isinstance(ch, str) and ch.isprintable():
                buf += ch
                self._draw_prompt(buf)

    # ------------------------------------------------------------------
    # Command handling
    # ------------------------------------------------------------------

    def _handle_input(self, text: str) -> None:
        if text.startswith("/"):
            self._handle_command(text)
        else:
            self._on_send(text)

    def _handle_command(self, text: str) -> None:
        cmd = text.strip().lower()
        if cmd == "/quit":
            self._running = False
            self._on_quit()
        elif cmd == "/peers":
            peers = self._get_peers()
            if peers:
                self.system_message("Known peers: " + ", ".join(peers))
            else:
                self.system_message("No known peers yet.")
        elif cmd == "/help":
            self.system_message("/quit — exit  |  /peers — list peers  |  /help — this message")
        else:
            self.system_message(f"Unknown command: {text}")
