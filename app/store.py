from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, TypeVar


T = TypeVar("T")
EMPTY_STORE: Dict[str, Any] = {"version": 1, "subscriptions": [], "deliveries": []}


class JsonStore:
    """A small, single-process JSON store with atomic file replacement."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()

    def read(self) -> Dict[str, Any]:
        with self._lock:
            return deepcopy(self._read_unlocked())

    def transact(self, operation: Callable[[Dict[str, Any]], T]) -> T:
        with self._lock:
            data = self._read_unlocked()
            result = operation(data)
            self._write_unlocked(data)
            return result

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
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(self.path))
