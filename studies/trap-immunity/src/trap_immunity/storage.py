"""An append-only JSONL file of rows, unique by a key, safe to resume."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Hashable, Iterator


class KeyedJsonl:
    """Rows appended one per line; a row whose key is already stored is skipped."""

    def __init__(self, path: Path, key: Callable[[dict[str, Any]], Hashable]) -> None:
        self.path = path
        self._key = key
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seen = {key(row) for row in self.read_all()}

    def __len__(self) -> int:
        return len(self._seen)

    def __contains__(self, key: Hashable) -> bool:
        return key in self._seen

    def add(self, row: dict[str, Any]) -> bool:
        key = self._key(row)
        if key in self._seen:
            return False
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        self._seen.add(key)
        return True

    def read_all(self) -> Iterator[dict[str, Any]]:
        """Every stored row, skipping a last line left truncated by a crash."""
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
