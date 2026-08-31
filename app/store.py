from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, TypeVar


T = TypeVar("T")
EMPTY_STORE: Dict[str, Any] = {"version": 1, "subscriptions": [], "deliveries": []}
LOCK_TIMEOUT_SECONDS = 30.0
LOCK_RETRY_SECONDS = 0.05


class JsonStore:
    """A small, single-process JSON store with atomic file replacement."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()

    def read(self) -> Dict[str, Any]:
        with self._lock:
            with self._process_lock():
                return deepcopy(self._read_unlocked())

    def transact(self, operation: Callable[[Dict[str, Any]], T]) -> T:
        with self._lock:
            with self._process_lock():
                data = self._read_unlocked()
                result = operation(data)
                self._write_unlocked(data)
                return result

    @contextmanager
    def _process_lock(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        with lock_path.open("a+b") as handle:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
            while True:
                try:
                    self._lock_file(handle)
                    break
                except (BlockingIOError, OSError):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("timed out waiting for JSON store lock")
                    time.sleep(LOCK_RETRY_SECONDS)
            try:
                yield
            finally:
                self._unlock_file(handle)

    @staticmethod
    def _lock_file(handle) -> None:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _unlock_file(handle) -> None:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _read_unlocked(self) -> Dict[str, Any]:
        if not self.path.exists():
            return deepcopy(EMPTY_STORE)
        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("JSON store root must be an object")
        data.setdefault("version", 1)
        data.setdefault("subscriptions", [])
        data.setdefault("deliveries", [])
        return data

    def _write_unlocked(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=str(self.path.parent), prefix=self.path.name + ".", suffix=".tmp",
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(str(temporary), str(self.path))
        finally:
            temporary.unlink(missing_ok=True)
