import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { useCountdown } from "../use-countdown";

describe("useCountdown", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns 0 when expiresAt is null", () => {
    const { result } = renderHook(() => useCountdown(null, "2026-07-25T12:00:00Z"));
    expect(result.current).toBe(0);
  });

  it("returns 0 when serverTime is null", () => {
    const { result } = renderHook(() => useCountdown("2026-07-26T12:00:00Z", null));
    expect(result.current).toBe(0);
  });

  it("calculates remaining seconds from server time offset", () => {
    const serverTime = "2026-07-25T10:00:00Z";
    const expiresAt = "2026-07-25T10:01:00Z"; // 60 seconds later
    const { result } = renderHook(() => useCountdown(expiresAt, serverTime));
    expect(result.current).toBe(60);
  });

  it("decrements by 1 each second", () => {
    const serverTime = "2026-07-25T10:00:00Z";
    const expiresAt = "2026-07-25T10:01:00Z";
    const { result } = renderHook(() => useCountdown(expiresAt, serverTime));
    expect(result.current).toBe(60);

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current).toBe(59);

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current).toBe(58);
  });

  it("floors to 0 when already expired", () => {
    const serverTime = "2026-07-25T12:00:00Z";
    const expiresAt = "2026-07-25T11:00:00Z"; // expired 1 hour ago
    const { result } = renderHook(() => useCountdown(expiresAt, serverTime));
    expect(result.current).toBe(0);
  });

  it("does not go below 0", () => {
    const serverTime = "2026-07-25T10:00:00Z";
    const expiresAt = "2026-07-25T10:00:01Z"; // 1 second left
    const { result } = renderHook(() => useCountdown(expiresAt, serverTime));
    expect(result.current).toBe(1);

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current).toBe(0);

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current).toBe(0);
  });

  it("resets countdown when props change", () => {
    const serverTime = "2026-07-25T10:00:00Z";
    const expiresAt1 = "2026-07-25T10:01:00Z";
    const expiresAt2 = "2026-07-25T10:02:00Z";

    const { result, rerender } = renderHook(
      ({ expiresAt, serverTime }) => useCountdown(expiresAt, serverTime),
      { initialProps: { expiresAt: expiresAt1, serverTime } },
    );
    expect(result.current).toBe(60);

    rerender({ expiresAt: expiresAt2, serverTime });
    expect(result.current).toBe(120);
  });
});
