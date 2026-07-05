import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useWhatsAppLinkPolling } from "../use-whatsapp-link-polling";

const mockGetStatus = vi.fn();

vi.mock("../../services/whatsapp-link-api", () => ({
  getWhatsAppLinkStatus: (...args: unknown[]) => mockGetStatus(...args),
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useWhatsAppLinkPolling", () => {
  const defaultOptions = {
    enabled: false,
    intervalMs: 5000,
    timeoutMs: 60000,
    onStatus: vi.fn(),
    onConnected: vi.fn(),
    onTimeout: vi.fn(),
    onError: vi.fn(),
  };

  it("polls immediately when enabled becomes true", async () => {
    mockGetStatus.mockResolvedValue({
      connected: false,
      phone: "+12015550000",
      instance_name: "test-instance",
    });

    const { result, rerender } = renderHook(
      (props) => useWhatsAppLinkPolling(props),
      { initialProps: { ...defaultOptions, enabled: false } },
    );

    expect(result.current.isPolling).toBe(false);

    // Enable polling
    rerender({ ...defaultOptions, enabled: true });

    // Should call immediately
    expect(mockGetStatus).toHaveBeenCalledTimes(1);
    expect(result.current.isPolling).toBe(true);
  });

  it("polls on the specified interval", async () => {
    mockGetStatus.mockResolvedValue({
      connected: false,
      phone: "+12015550000",
      instance_name: "test-instance",
    });

    renderHook(() => useWhatsAppLinkPolling({ ...defaultOptions, enabled: true }));

    expect(mockGetStatus).toHaveBeenCalledTimes(1);

    // Advance 5 seconds
    await act(async () => {
      vi.advanceTimersByTime(5000);
    });
    expect(mockGetStatus).toHaveBeenCalledTimes(2);

    // Advance another 5 seconds
    await act(async () => {
      vi.advanceTimersByTime(5000);
    });
    expect(mockGetStatus).toHaveBeenCalledTimes(3);
  });

  it("stops polling and calls onConnected once when connected becomes true", async () => {
    const onConnected = vi.fn();
    mockGetStatus
      .mockResolvedValueOnce({
        connected: false,
        phone: "+12015550000",
        instance_name: "test-instance",
      })
      .mockResolvedValueOnce({
        connected: true,
        phone: "+12015550000",
        instance_name: "test-instance",
      });

    const { result } = renderHook(() =>
      useWhatsAppLinkPolling({ ...defaultOptions, enabled: true, onConnected }),
    );

    // First call returned disconnected
    expect(mockGetStatus).toHaveBeenCalledTimes(1);
    expect(onConnected).not.toHaveBeenCalled();

    // Advance to next poll - should get connected=true
    await act(async () => {
      vi.advanceTimersByTime(5000);
    });

    expect(onConnected).toHaveBeenCalledTimes(1);
    expect(onConnected).toHaveBeenCalledWith({
      connected: true,
      phone: "+12015550000",
      instance_name: "test-instance",
    });

    // Should have stopped polling
    const callsAfterConnected = mockGetStatus.mock.calls.length;
    await act(async () => {
      vi.advanceTimersByTime(15000);
    });
    expect(mockGetStatus.mock.calls.length).toBe(callsAfterConnected);
    expect(result.current.isPolling).toBe(false);
  });

  it("calls onTimeout after timeoutMs elapses without connected", async () => {
    const onTimeout = vi.fn();
    mockGetStatus.mockResolvedValue({
      connected: false,
      phone: "+12015550000",
      instance_name: "test-instance",
    });

    renderHook(() =>
      useWhatsAppLinkPolling({ ...defaultOptions, enabled: true, onTimeout }),
    );

    // Advance just before timeout
    await act(async () => {
      vi.advanceTimersByTime(59000);
    });
    expect(onTimeout).not.toHaveBeenCalled();

    // Advance to timeout
    await act(async () => {
      vi.advanceTimersByTime(1000);
    });
    expect(onTimeout).toHaveBeenCalledTimes(1);
  });

  it("clears timers on unmount", async () => {
    mockGetStatus.mockResolvedValue({
      connected: false,
      phone: "+12015550000",
      instance_name: "test-instance",
    });

    const { unmount } = renderHook(() =>
      useWhatsAppLinkPolling({ ...defaultOptions, enabled: true }),
    );

    expect(mockGetStatus).toHaveBeenCalledTimes(1);

    unmount();

    // Advance time - should not trigger more calls
    mockGetStatus.mockClear();
    await act(async () => {
      vi.advanceTimersByTime(10000);
    });
    expect(mockGetStatus).not.toHaveBeenCalled();
  });

  it("surfaces transient errors through onError and continues polling", async () => {
    const onError = vi.fn();
    const error = new Error("Network error");
    mockGetStatus
      .mockRejectedValueOnce(error)
      .mockResolvedValueOnce({
        connected: false,
        phone: "+12015550000",
        instance_name: "test-instance",
      });

    renderHook(() =>
      useWhatsAppLinkPolling({ ...defaultOptions, enabled: true, onError }),
    );

    // First call rejected
    await act(async () => {
      vi.advanceTimersByTime(5000);
    });
    expect(onError).toHaveBeenCalledWith(error);

    // Second call resolves - should still be polling
    await act(async () => {
      vi.advanceTimersByTime(5000);
    });
    expect(mockGetStatus).toHaveBeenCalledTimes(3);
  });

  it("returns stop function that halts polling", async () => {
    mockGetStatus.mockResolvedValue({
      connected: false,
      phone: "+12015550000",
      instance_name: "test-instance",
    });

    const { result } = renderHook(() =>
      useWhatsAppLinkPolling({ ...defaultOptions, enabled: true }),
    );

    expect(mockGetStatus).toHaveBeenCalledTimes(1);

    await act(async () => {
      result.current.stop();
    });

    mockGetStatus.mockClear();
    await act(async () => {
      vi.advanceTimersByTime(10000);
    });
    expect(mockGetStatus).not.toHaveBeenCalled();
    expect(result.current.isPolling).toBe(false);
  });
});
