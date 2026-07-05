import api from "@/lib/api";

export interface WhatsAppLinkStatus {
  connected: boolean;
  phone: string | null;
  instance_name: string;
}

export interface PairingCodeResponse {
  code: string;
}

export interface QRCodeResponse {
  qrcode: string;
}

export interface DisconnectResponse {
  connected: false;
}

export async function getWhatsAppLinkStatus(): Promise<WhatsAppLinkStatus> {
  const { data } = await api.get<WhatsAppLinkStatus>("/tenant/whatsapp-link/status");
  return data;
}

export async function requestPairingCode(): Promise<PairingCodeResponse> {
  const { data } = await api.post<PairingCodeResponse>("/tenant/whatsapp-link/pair", {});
  return data;
}

export async function getQRCode(): Promise<QRCodeResponse> {
  const { data } = await api.get<QRCodeResponse>("/tenant/whatsapp-link/qr");
  return data;
}

export async function disconnectWhatsApp(): Promise<DisconnectResponse> {
  const { data } = await api.post<DisconnectResponse>("/tenant/whatsapp-link/disconnect");
  return data;
}
