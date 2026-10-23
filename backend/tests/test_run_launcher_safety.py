"""The desktop launcher must never kill Docker/WSL to reclaim an API port."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

import run as launcher


class _FakePsutilError(Exception):
    pass


class _FakeProcess:
    def __init__(self, *, pid: int, name: str, exe: str, port: int):
        self.pid = pid
        self.info = {"pid": pid, "name": name}
        self._exe = exe
        self._port = port
        self.killed = False

    def net_connections(self, kind: str):
        assert kind == "inet"
        return [SimpleNamespace(laddr=SimpleNamespace(port=self._port))]

    def cwd(self):
        return "C:\\Windows"

    def exe(self):
        return self._exe

    def cmdline(self):
        return [self._exe]

    def kill(self):
        self.killed = True


def _fake_psutil(monkeypatch, process: _FakeProcess):
    fake = SimpleNamespace(
        process_iter=lambda _attrs: [process],
        NoSuchProcess=_FakePsutilError,
        AccessDenied=_FakePsutilError,
    )
    monkeypatch.setitem(sys.modules, "psutil", fake)


def test_kill_port_refuses_docker_owner(monkeypatch):
    process = _FakeProcess(
        pid=100,
        name="com.docker.backend.exe",
        exe="C:\\Program Files\\Docker\\Docker\\resources\\com.docker.backend.exe",
        port=8000,
    )
    _fake_psutil(monkeypatch, process)

    with pytest.raises(launcher.PortInUseError, match="will not terminate Docker"):
        launcher.kill_port(8000)

    assert process.killed is False


def test_kill_port_terminates_stale_project_child(monkeypatch):
    process = _FakeProcess(
        pid=101,
        name="python.exe",
        exe=str(launcher.PYTHON),
        port=8000,
    )
    _fake_psutil(monkeypatch, process)

    launcher.kill_port(8000)

    assert process.killed is True
