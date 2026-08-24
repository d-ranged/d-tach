"""Tests for tray.py helpers that don't require an actual tray icon or GUI."""

import socket

from tray import _is_port_available


class TestIsPortAvailable:
    def test_free_port_is_available(self) -> None:
        # Bind to port 0 to let the OS hand back a genuinely free port, then release it.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            free_port = probe.getsockname()[1]

        assert _is_port_available(free_port) is True

    def test_occupied_port_is_not_available(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
            holder.bind(("127.0.0.1", 0))
            holder.listen(1)
            occupied_port = holder.getsockname()[1]

            assert _is_port_available(occupied_port) is False
