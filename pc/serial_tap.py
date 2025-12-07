from __future__ import annotations

import socket
import threading
from contextlib import suppress


class SerialTapServer:
    """
    Lightweight TCP broadcast server that mirrors every serial line that
    passes through SerialManager. This lets you connect with telnet/netcat
    while the PC app keeps exclusive ownership of the USB CDC port.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self._lock = threading.Lock()
        self._clients: set[socket.socket] = set()
        self._running = True

        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((self.host, self.port))
        self._server.listen()

        self._accept_thread = threading.Thread(
            target=self._accept_loop, name="SerialTapAccept", daemon=True
        )
        self._accept_thread.start()

    def _accept_loop(self):
        while self._running:
            try:
                client, _ = self._server.accept()
            except OSError:
                break

            client.setblocking(True)
            with self._lock:
                self._clients.add(client)

            threading.Thread(
                target=self._drain_client,
                args=(client,),
                name="SerialTapClient",
                daemon=True,
            ).start()

    def _drain_client(self, client: socket.socket):
        try:
            while self._running:
                data = client.recv(1024)
                if not data:
                    break
        except OSError:
            pass
        finally:
            with self._lock:
                self._clients.discard(client)
            with suppress(OSError):
                client.close()

    def broadcast(self, direction: str, payload: str):
        """
        Send a line to every connected tap client. Direction should be 'TX' or 'RX'.
        """
        if not payload:
            return

        message = f"[{direction}] {payload}\r\n".encode("utf-8", errors="replace")

        with self._lock:
            clients = list(self._clients)

        for client in clients:
            try:
                client.sendall(message)
            except OSError:
                with self._lock:
                    self._clients.discard(client)
                with suppress(OSError):
                    client.close()

    def close(self):
        self._running = False
        with suppress(OSError):
            self._server.close()

        with self._lock:
            clients = list(self._clients)
            self._clients.clear()

        for client in clients:
            with suppress(OSError):
                client.close()

