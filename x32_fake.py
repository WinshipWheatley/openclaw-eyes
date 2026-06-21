"""In-memory FAKE of an X32 desk over OSC/UDP — test double for Niles' controller.

Mimics the X32 semantics we rely on: a message WITH args sets the value at that
address; a message with NO args is a query and the desk replies with the stored
value. Real UDP on localhost, ephemeral port. Swap for Maillot's emulator or a
real console later — same wire interface.
"""
import socket
import threading

from osc_codec import encode, decode


class X32Fake:
    def __init__(self, host="127.0.0.1", port=0):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.host, self.port = self.sock.getsockname()
        self.state = {}            # address -> [args]
        self.state["/xinfo"] = ["192.168.50.99", "X32FAKE", "X32 Rack", "4.06-fake"]
        self._run = False
        self._t = None

    def start(self):
        self._run = True
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()
        return self

    def stop(self):
        self._run = False
        try:
            self.sock.close()
        except OSError:
            pass

    def _loop(self):
        while self._run:
            try:
                data, peer = self.sock.recvfrom(65535)
            except OSError:
                break
            try:
                address, args = decode(data)
            except Exception:
                continue
            if args:                          # set
                self.state[address] = args
            else:                             # query -> reply
                val = self.state.get(address)
                reply = encode(address, *val) if val is not None else encode(address)
                try:
                    self.sock.sendto(reply, peer)
                except OSError:
                    pass
