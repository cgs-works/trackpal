import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/lib/api";
import {
  getWhatsAppLinkStatus,
  requestPairingCode,
  getQRCode,
  disconnectWhatsApp,
} from "../whatsapp-link-api";

vi.mock("@/lib/api", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

describe("WhatsApp Link API service", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("getWhatsAppLinkStatus calls GET /tenant/whatsapp-link/status and returns typed response", async () => {
    const expected = { connected: true, phone: "+12015550000", instance_name: "tenant-instance" };
    mockedApi.get.mockResolvedValueOnce({ data: expected });

    const result = await getWhatsAppLinkStatus();
    expect(result).toEqual(expected);
    expect(mockedApi.get).toHaveBeenCalledWith("/tenant/whatsapp-link/status");
  });

  it("getWhatsAppLinkStatus returns phone: null when not configured", async () => {
    const expected = { connected: false, phone: null, instance_name: "tenant-instance" };
    mockedApi.get.mockResolvedValueOnce({ data: expected });

    const result = await getWhatsAppLinkStatus();
    expect(result.phone).toBeNull();
  });

  it("requestPairingCode calls POST /tenant/whatsapp-link/pair with {} and returns code", async () => {
    const expected = { code: "12345678" };
    mockedApi.post.mockResolvedValueOnce({ data: expected });

    const result = await requestPairingCode();
    expect(result).toEqual(expected);
    expect(mockedApi.post).toHaveBeenCalledWith("/tenant/whatsapp-link/pair", {});
  });

  it("getQRCode calls GET /tenant/whatsapp-link/qr and returns qrcode", async () => {
    const expected = { qrcode: "iVBORw0KGgo..." };
    mockedApi.get.mockResolvedValueOnce({ data: expected });

    const result = await getQRCode();
    expect(result).toEqual(expected);
    expect(mockedApi.get).toHaveBeenCalledWith("/tenant/whatsapp-link/qr");
  });

  it("disconnectWhatsApp calls POST /tenant/whatsapp-link/disconnect and returns connected:false", async () => {
    const expected = { connected: false };
    mockedApi.post.mockResolvedValueOnce({ data: expected });

    const result = await disconnectWhatsApp();
    expect(result).toEqual(expected);
    expect(mockedApi.post).toHaveBeenCalledWith("/tenant/whatsapp-link/disconnect");
  });
});
