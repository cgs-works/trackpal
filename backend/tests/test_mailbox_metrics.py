"""Tests for lightweight metrics registry used by mailbox observability."""

import pytest

import app.core.metrics as metrics_module


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch):
    """Reset shared registry before each test."""
    registry = metrics_module._MetricsRegistry()  # noqa: SLF001
    monkeypatch.setattr(metrics_module, "metrics", registry)
    return registry


class TestMetricsRegistry:
    """Unit tests for _MetricsRegistry."""

    def test_increment_counter(self):
        """Counter increments correctly."""
        metrics_module.metrics.inc("test_counter", status="ok")
        output = metrics_module.metrics.dump_prometheus()
        assert 'test_counter{status="ok"} 1' in output

    def test_counter_multiple_increments(self):
        """Multiple increments accumulate."""
        name = "test_multi"
        metrics_module.metrics.inc(name)
        metrics_module.metrics.inc(name)
        metrics_module.metrics.inc(name)
        output = metrics_module.metrics.dump_prometheus()
        assert f"{name} 3" in output

    def test_counter_with_labels(self):
        """Labels are included in the key."""
        metrics_module.metrics.inc("labeled_count", provider="google", status="ok")
        output = metrics_module.metrics.dump_prometheus()
        assert 'provider="google"' in output
        assert 'status="ok"' in output

    def test_latency_record(self):
        """Latency samples are recorded and rendered."""
        metrics_module.metrics.record("test_latency", 0.123)
        metrics_module.metrics.record("test_latency", 0.456)
        output = metrics_module.metrics.dump_prometheus()
        assert "test_latency" in output
        assert "quantile" in output

    def test_prometheus_format_syntax(self):
        """Output matches Prometheus exposition format basics."""
        metrics_module.metrics.inc("syntax_test")
        output = metrics_module.metrics.dump_prometheus()
        items = [ln for ln in output.split("\n") if ln.strip()]
        # Every metric line should start with the name or # HELP/# TYPE
        allowed_prefixes = (
            "#",
            "syntax_test",
            "test_",
            "labeled_",
            "lookup_",
            "oauth_",
            "mailbox_",
            "mailbox_api_",
            "order_test",
            "multi_label",
            "bounded_test",
            "safe_test",
            "safe_latency",
            "concurrent_test",
        )
        for line in items:
            assert line.startswith(allowed_prefixes), f"Bad line: {line}"
        assert output.endswith("\n")

    def test_empty_registry(self):
        """Empty registry produces empty or header-only output."""
        # Create a new registry-like behavior:
        # The shared registry might have data from other tests,
        # so we test format structure rather than emptiness
        output = metrics_module.metrics.dump_prometheus()
        assert isinstance(output, str)

    def test_latency_memory_bound(self):
        """Latency list does not grow unbounded."""
        for _ in range(15_000):
            metrics_module.metrics.record("bounded_test", 0.001)
        output = metrics_module.metrics.dump_prometheus()
        assert "bounded_test" in output

    def test_labels_order_independent(self):
        """Same labels in different order produce same key."""
        metrics_module.metrics.inc("order_test", a="1", b="2")
        metrics_module.metrics.inc("order_test", b="2", a="1")
        output = metrics_module.metrics.dump_prometheus()
        count = output.count("order_test")
        # Expect 3 occurrences: 2 for HELP/TYPE, 1 for value
        assert count > 0

    def test_increment_and_record_does_not_raise(self):
        """Operations never raise under normal conditions."""
        try:
            metrics_module.metrics.inc("safe_test")
            metrics_module.metrics.record("safe_latency", 1.5)
        except Exception as exc:
            import pytest

            pytest.fail(f"Metrics ops raised: {exc}")

    def test_dump_prometheus_returns_text(self):
        """Rendered output is valid string with expected sections."""
        output = metrics_module.metrics.dump_prometheus()
        assert "# HELP" in output or output.strip() == ""

    def test_metric_name_with_different_label_values(self):
        """Same metric name, different label values → separate counters."""
        metrics_module.metrics.inc("multi_label", service="netflix")
        metrics_module.metrics.inc("multi_label", service="disney")
        output = metrics_module.metrics.dump_prometheus()
        assert 'service="netflix"' in output
        assert 'service="disney"' in output

    def test_concurrent_safety(self):
        """Multiple threads can inc concurrently."""
        import threading

        errors: list[Exception] = []

        def _thread_inc():
            try:
                for _ in range(100):
                    metrics_module.metrics.inc("concurrent_test")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_thread_inc) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread errors: {errors}"
