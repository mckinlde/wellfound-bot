from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional


class BotLogger:
    def __init__(self, success_path: Path, fail_path: Path, tee_stdout: bool = True):
        self.success_path = success_path
        self.fail_path = fail_path
        self.tee = tee_stdout
        self.success_path.parent.mkdir(parents=True, exist_ok=True)
        self.fail_path.parent.mkdir(parents=True, exist_ok=True)

    def _stamp(self) -> str:
        # ISO-like, local time
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _write(self, path: Path, line: str):
        path.write_text(
            (path.read_text(encoding="utf-8") if path.exists() else "") + line,
            encoding="utf-8",
        )

    def info(self, msg: str):
        line = f"{self._stamp()} [INFO] {msg}\n"
        if self.tee:
            print(line, end="")
        self._write(self.success_path, line)

    def success(self, msg: str):
        line = f"{self._stamp()} [SUCCESS] {msg}\n"
        if self.tee:
            print(line, end="")
        self._write(self.success_path, line)

    def fail(self, msg: str):
        line = f"{self._stamp()} [FAIL] {msg}\n"
        if self.tee:
            print(line, end="")
        self._write(self.fail_path, line)
