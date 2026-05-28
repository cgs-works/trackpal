"""Lightweight in-process metrics for mailbox operations.

Uses stdlib only — no external dependencies. Counter + latency
tracking exposed via ``/metrics`` Prometheus-style text endpoint.
"""

from __future__ import annotations

import threading
from collections import defaultdict


class _MetricsRegistry:
    """Thread-safe metrics registry with counters and latency buckets."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._latencies: dict[str, list[float]] = defaultdict(list)

    def inc(self, name: str, **labels: str) -> None:
        """Increment a named counter with optional label dimensions."""
        key = name
        if labels:
            parts = sorted(f'{k}="{v}"' for k, v in labels.items())
            key = f"{name}{{{','.join(parts)}}}"
        with self._lock:
            self._counters[key] += 1

    def record(self, name: str, duration_s: float) -> None:
        """Record a latency sample (in seconds)."""
        with self._lock:
            self._latencies[name].append(duration_s)
            # bounded memory: keep last 10k samples
            if len(self._latencies[name]) > 10_000:
                self._latencies[name] = self._latencies[name][-5_000:]

    def dump_prometheus(self) -> str:
        """Render all metrics as Prometheus exposition format text."""
        lines: list[str] = []
        with self._lock:
            for key, val in sorted(self._counters.items()):
                name = key.split("{", 1)[0]
                lines.append(f"# HELP {name} Counter")
                lines.append(f"# TYPE {name} counter")
                lines.append(f"{key} {val}")
            for name, vals in sorted(self._latencies.items()):
                if not vals:
                    continue
                total = sum(vals)
                cnt = len(vals)
                lines.append(f"# HELP {name}_latency_seconds Latency in seconds")
                lines.append(f"# TYPE {name}_latency_seconds gauge")
                lines.append(
                    f'{name}_latency_seconds{{quantile="p50"}} {sorted(vals)[cnt // 2]:.4f}'
                )
                lines.append(
                    f'{name}_latency_seconds{{quantile="avg"}} {(total / cnt):.4f}'
                )
                lines.append(f'{name}_latency_seconds{{quantile="count"}} {cnt}')
        return "\n".join(lines) + "\n"


metrics = _MetricsRegistry()

__all__ = ["metrics"]
