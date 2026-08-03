import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProfileSection } from "../profile-section";

vi.mock("@/i18n", () => ({
  t: (key: string) => key,
}));

const profile = {
  id: "tenant-1",
  full_name: "Demo Account",
  email: "demo@example.com",
  phone: "12015550000",
  role: "tenant",
  username: "demo",
  name: null,
  tenant_id: null,
  tenant_name: null,
  client_prefix: null,
  locale: null,
  timezone: null,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("ProfileSection", () => {
  it("exposes the stable profile target used by the orientation tour", () => {
    const { container } = render(
      <ProfileSection profile={profile} onProfileUpdate={vi.fn()} />,
    );

    expect(
      container.querySelector('[data-help-id="admin.settings.profile"]'),
    ).toBeInTheDocument();
  });
});
