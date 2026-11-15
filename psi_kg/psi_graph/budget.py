"""Bound original-file scratch usage and preserve filesystem headroom."""

import math
import shutil
from contextvars import ContextVar
from pathlib import Path

active_budget = ContextVar("psi_storage_budget", default=None)


class StorageLimitError(RuntimeError):
    pass


def positive_gb(value):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Storage limits must be finite positive GB values")
    return value


class StorageBudget:
    def __init__(self, root, limit_bytes, reserve_bytes):
        self.root = Path(root)
        self.limit = limit_bytes
        self.reserve = reserve_bytes
        self.paths = set()
        self.peak = 0

    @property
    def used(self):
        self.paths = {p for p in self.paths if p.is_file()}
        return sum(p.stat().st_size for p in self.paths)

    def free_check(self, additional):
        free = shutil.disk_usage(self.root).free
        if free - additional < self.reserve:
            raise StorageLimitError(
                f"Insufficient free disk space: need {additional / 1e9:.3f} GB plus "
                f"{self.reserve / 1e9:.3f} GB reserve; {free / 1e9:.3f} GB free. "
                "Free space or increase the disk before resuming."
            )

    def check(self, additional):
        used = self.used
        if used + additional > self.limit:
            raise StorageLimitError(
                f"Original-file storage would exceed {self.limit / 1e9:.3f} GB "
                f"({used / 1e9:.3f} GB in use, {additional / 1e9:.3f} GB needed). "
                "This file/member requires more space; no data was silently skipped. "
                "Increase --max-temp-gb only if disk space permits."
            )
        self.free_check(additional)

    def track(self, path):
        self.paths.add(Path(path))

    def write(self, stream, block):
        self.track(stream.name)
        self.check(len(block))
        stream.write(block)
        stream.flush()
        self.peak = max(self.peak, self.used)


def guarded_write(stream, block):
    budget = active_budget.get()
    if budget is None:
        stream.write(block)
    else:
        budget.write(stream, block)
