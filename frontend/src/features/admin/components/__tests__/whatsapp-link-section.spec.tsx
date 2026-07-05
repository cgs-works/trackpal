import { render, screen, waitFor, act, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { WhatsappLinkSection } from "../whatsapp-link-section";

// ---- Module-level mocks ----

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const mockGetStatus = vi.fn();
const mockRequestPair = vi.fn();
const mockGetQR = vi.fn();
const mockDisconnect = vi.fn();

vi.mock("../../services/whatsapp-link-api", () => ({
  getWhatsAppLinkStatus: (...args: unknown[]) => mockGetStatus(...args),
  requestPairingCode: (...args: unknown[]) => mockRequestPair(...args),
  getQRCode: (...args: unknown[]) => mockGetQR(...args),
  disconnectWhatsApp: (...args: unknown[]) => mockDisconnect(...args),
}));

// Polling hook mock — we capture options to simulate onConnected/onTimeout
const mockUsePolling = vi.fn().mockReturnValue({
  isPolling: false,
  elapsedMs: 0,
  stop: vi.fn(),
});

vi.mock("../../hooks/use-whatsapp-link-polling", () => ({
  useWhatsAppLinkPolling: (...args: unknown[]) => mockUsePolling(...args),
}));

// ---- Test data helpers ----

const connectedStatus = {
  connected: true,
  phone: "+12015550000",
  instance_name: "test-instance",
};

const disconnectedStatus = {
  connected: false,
  phone: "+12015550000",
  instance_name: "test-instance",
};

const noPhoneStatus = {
  connected: false,
  phone: null,
  instance_name: "test-instance",
};

// ---- Suite ----

describe("WhatsappLinkSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUsePolling.mockReturnValue({
      isPolling: false,
      elapsedMs: 0,
      stop: vi.fn(),
    });
  });

  describe("Loading and error states", () => {
    it("shows a skeleton while loading then renders status content", async () => {
      mockGetStatus.mockResolvedValue(connectedStatus);

      render(<WhatsappLinkSection />);

      // Skeleton is present during initial render
      expect(document.querySelector('[data-slot="skeleton"]')).toBeInTheDocument();

      // Await the phone value (the label includes a colon appended to the t() result)
      await waitFor(() => {
        expect(screen.getByText(/frontend\.whatsapp_link\.phone_label/)).toBeInTheDocument();
      });

      // Skeleton should be gone
      expect(document.querySelector('[data-slot="skeleton"]')).not.toBeInTheDocument();
    });

    it("displays the backend error detail when load fails", async () => {
      const apiError = { response: { data: { detail: "Instance not configured" } } };
      mockGetStatus.mockRejectedValue(apiError);

      render(<WhatsappLinkSection />);

      await waitFor(() => {
        expect(screen.getByText("Instance not configured")).toBeInTheDocument();
      });
    });

    it("displays a fallback translated error when no backend detail is present", async () => {
      mockGetStatus.mockRejectedValue(new Error("Network Error"));

      render(<WhatsappLinkSection />);

      await waitFor(() => {
        const matches = screen.getAllByText("frontend.whatsapp_link.error_load");
            expect(matches.length).toBeGreaterThanOrEqual(1);
      });

      // Retry button should be available
      expect(screen.getByRole("button", { name: "frontend.whatsapp_link.retry" })).toBeInTheDocument();
    });
  });

  describe("Connected state", () => {
    it("shows the connected badge, phone, instance name, and Disconnect button", async () => {
      mockGetStatus.mockResolvedValue(connectedStatus);

      render(<WhatsappLinkSection />);

      await waitFor(() => {
        expect(screen.getByText("frontend.whatsapp_link.status_connected")).toBeInTheDocument();
      });

      expect(screen.getByText("+12015550000")).toBeInTheDocument();
      expect(screen.getByText("test-instance")).toBeInTheDocument();
      expect(screen.getByText("frontend.whatsapp_link.disconnect")).toBeInTheDocument();
    });
  });

  describe("Disconnected state", () => {
    it("shows the disconnected badge and pairing tabs when phone is configured", async () => {
      mockGetStatus.mockResolvedValue(disconnectedStatus);

      render(<WhatsappLinkSection />);

      await waitFor(() => {
        expect(screen.getByText("frontend.whatsapp_link.status_disconnected")).toBeInTheDocument();
      });

      expect(screen.getByText("frontend.whatsapp_link.pairing_tab")).toBeInTheDocument();
      expect(screen.getByText("frontend.whatsapp_link.qr_tab")).toBeInTheDocument();
    });

    it("shows a no-phone alert and hides the pairing UI when phone is null", async () => {
      mockGetStatus.mockResolvedValue(noPhoneStatus);

      render(<WhatsappLinkSection />);

      await waitFor(() => {
        expect(screen.getByText("frontend.whatsapp_link.no_phone_title")).toBeInTheDocument();
      });

      expect(screen.queryByText("frontend.whatsapp_link.pairing_tab")).not.toBeInTheDocument();
      expect(screen.queryByText("frontend.whatsapp_link.qr_tab")).not.toBeInTheDocument();
    });
  });

  describe("Pairing code flow", () => {
    it("requests a pairing code and displays the 8-digit code", async () => {
      mockGetStatus.mockResolvedValue(disconnectedStatus);
      mockRequestPair.mockResolvedValue({ code: "12345678" });

      render(<WhatsappLinkSection />);

      await waitFor(() => {
        expect(screen.getByText("frontend.whatsapp_link.status_disconnected")).toBeInTheDocument();
      });

      // Click Generate Code button
      await userEvent.click(screen.getByText("frontend.whatsapp_link.generate_code"));

      expect(mockRequestPair).toHaveBeenCalledTimes(1);

      // The 8-digit code should be displayed prominently
      await waitFor(() => {
        expect(screen.getByText("12345678")).toBeInTheDocument();
      });

      // Polling should have been enabled
      expect(mockUsePolling).toHaveBeenCalledWith(
        expect.objectContaining({ enabled: true }),
      );
    });

    it("transitions to connected state and shows toast when polling succeeds", async () => {
      mockGetStatus.mockResolvedValue(disconnectedStatus);
      mockRequestPair.mockResolvedValue({ code: "12345678" });

      render(<WhatsappLinkSection />);

      await waitFor(() => {
        expect(screen.getByText("frontend.whatsapp_link.status_disconnected")).toBeInTheDocument();
      });

      await userEvent.click(screen.getByText("frontend.whatsapp_link.generate_code"));

      // Capture the polling options
      const pollingOptions = mockUsePolling.mock.lastCall?.[0];
      expect(pollingOptions?.enabled).toBe(true);

      // Simulate a successful connection
      await act(async () => {
        pollingOptions.onConnected(connectedStatus);
      });

      // Should now show connected state
      await waitFor(() => {
        expect(screen.getByText("frontend.whatsapp_link.status_connected")).toBeInTheDocument();
      });

      // Toast should have been shown
      expect(toast.success).toHaveBeenCalledWith("frontend.whatsapp_link.success_linked");
    });

    it("shows a timeout alert with a retry action when polling times out", async () => {
      mockGetStatus.mockResolvedValue(disconnectedStatus);
      mockRequestPair.mockResolvedValue({ code: "12345678" });

      render(<WhatsappLinkSection />);

      await waitFor(() => {
        expect(screen.getByText("frontend.whatsapp_link.status_disconnected")).toBeInTheDocument();
      });

      await userEvent.click(screen.getByText("frontend.whatsapp_link.generate_code"));

      const pollingOptions = mockUsePolling.mock.lastCall?.[0];

      // Simulate timeout
      await act(async () => {
        pollingOptions.onTimeout();
      });

      // Timeout error should be visible
      expect(screen.getByText("frontend.whatsapp_link.error_timeout")).toBeInTheDocument();

      // Retry button should be present
      expect(screen.getByRole("button", { name: "frontend.whatsapp_link.retry" })).toBeInTheDocument();
    });
  });

  describe("QR code flow", () => {
    it("loads a QR code image with a base64 data URL when the QR tab is activated", async () => {
      mockGetStatus.mockResolvedValue(disconnectedStatus);
      mockGetQR.mockResolvedValue({
        qrcode: "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
      });

      render(<WhatsappLinkSection />);

      await waitFor(() => {
        expect(screen.getByText("frontend.whatsapp_link.status_disconnected")).toBeInTheDocument();
      });

      // Click QR tab
      await userEvent.click(screen.getByText("frontend.whatsapp_link.qr_tab"));

      // Click the "Refresh QR" button to load the QR code
      await userEvent.click(screen.getByText("frontend.whatsapp_link.refresh_qr"));

      // Wait for QR image to load
      await waitFor(() => {
        const img = screen.getByRole("img", { name: "frontend.whatsapp_link.qr_alt" });
        expect(img).toHaveAttribute(
          "src",
          "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        );
      });

      // Polling should have been enabled
      expect(mockUsePolling).toHaveBeenCalledWith(
        expect.objectContaining({ enabled: true }),
      );
    });
  });

  describe("Disconnect flow", () => {
    it("shows a confirmation dialog and calls the disconnect API on confirm", async () => {
      // Set up mocks: initial load returns connected; after disconnect reload returns disconnected
      mockGetStatus
        .mockResolvedValueOnce(connectedStatus)
        .mockResolvedValueOnce(disconnectedStatus);

      mockDisconnect.mockResolvedValue({ connected: false });

      render(<WhatsappLinkSection />);

      // Wait for connected state to show
      await waitFor(() => {
        expect(screen.getByText("frontend.whatsapp_link.status_connected")).toBeInTheDocument();
      });

      // Click the Disconnect trigger button (uses aria-label)
      await userEvent.click(screen.getByRole("button", { name: "frontend.whatsapp_link.disconnect" }));

      // Confirmation dialog should appear
      expect(screen.getByText("frontend.whatsapp_link.disconnect_confirm_title")).toBeInTheDocument();
      expect(screen.getByText("frontend.whatsapp_link.disconnect_confirm_description")).toBeInTheDocument();

      // Click the confirm action button inside the dialog
      const dialog = screen.getByRole("alertdialog");
      await userEvent.click(within(dialog).getByText("frontend.whatsapp_link.disconnect"));

      // Should call the disconnect API
      expect(mockDisconnect).toHaveBeenCalledTimes(1);

      // Should reload status after disconnect — status becomes disconnected
      await waitFor(() => {
        expect(mockGetStatus).toHaveBeenCalledTimes(2);
      });

      // After reload, should show disconnected status
      await waitFor(() => {
        expect(screen.getByText("frontend.whatsapp_link.status_disconnected")).toBeInTheDocument();
      });
    });
  });
});
