"""Test harness for Actual Budget v26.10.0 (system under test).

Each test module gets a FRESH server with its own data directory, so tests never depend on each other.
The server rate-limits per client IP. API tests that need "different clients" bind the TCP source address
to a different loopback IP (127.0.0.N) with `client(ip)`. Note: merely connecting TO 127.0.0.N is not enough,
the source would still be 127.0.0.1 (this exact mistake produced a false "global lockout" finding during
exploration, see docs/test-summary-report.md).
"""
import itertools
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import pytest
import requests
from requests.adapters import HTTPAdapter

ACTUAL_DIR = Path(os.getenv("ACTUAL_DIR", "../sut")).resolve()  # folder where `npm i @actual-app/sync-server@26.10.0` was run
SERVER_BIN = ACTUAL_DIR / "node_modules" / ".bin" / "actual-server"
PASSWORD = "qc-Password-1"
_ips = itertools.count(20)


class _SourceAddressAdapter(HTTPAdapter):
    def __init__(self, ip, **kw):
        self._ip = ip
        super().__init__(**kw)

    def init_poolmanager(self, *a, **kw):
        kw["source_address"] = (self._ip, 0)
        return super().init_poolmanager(*a, **kw)


def client(ip: str = "127.0.0.1") -> requests.Session:
    """HTTP session whose requests really originate from `ip`."""
    sess = requests.Session()
    sess.mount("http://", _SourceAddressAdapter(ip))
    return sess


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def next_ip() -> str:
    return f"127.0.0.{next(_ips) % 230 + 20}"


class Server:
    def __init__(self, hostname="0.0.0.0", env=None, bootstrap=True):
        self.port = free_port()
        self.data = Path(tempfile.mkdtemp(prefix="actual-qc-"))
        self.log = self.data / "server.log"
        full_env = {**os.environ, "ACTUAL_HOSTNAME": hostname, "ACTUAL_PORT": str(self.port),
                    "ACTUAL_DATA_DIR": str(self.data), **(env or {})}
        self._log_file = open(self.log, "w")  # noqa: SIM115  closed in stop(); the server writes to it
        self.proc = subprocess.Popen([str(SERVER_BIN)], cwd=self.data, env=full_env,
                                     stdout=self._log_file, stderr=subprocess.STDOUT)
        self.hostname = hostname
        if hostname != "::":
            self._wait()
            if bootstrap:
                r = requests.post(self.url() + "/account/bootstrap", json={"password": PASSWORD}, timeout=10)
                assert r.json()["status"] == "ok", r.text

    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def _wait(self):
        for _ in range(150):
            try:
                requests.get(self.url() + "/info", timeout=1)
                return
            except requests.ConnectionError:
                time.sleep(0.2)
        raise RuntimeError(self.log.read_text())

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(timeout=10)
        self._log_file.close()
        shutil.rmtree(self.data, ignore_errors=True)


@pytest.fixture(scope="module")
def server():
    s = Server()
    yield s
    s.stop()


@pytest.fixture
def fresh_server():
    """Not bootstrapped: for tests of the first-time password setup."""
    s = Server(bootstrap=False)
    yield s
    s.stop()
