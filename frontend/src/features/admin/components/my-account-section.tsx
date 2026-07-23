import { t } from "@/i18n";
import { useAuthStore } from "@/store/auth";
import { PasswordSection } from "../components/password-section";
import { ProfileSection } from "../components/profile-section";
import { DataTabContent } from "../components/data-tab-content";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  type Profile,
  type ProfileUpdate,
  updateProfile,
  updateTenantProfile,
} from "../services/settings-api";

interface MyAccountSectionProps {
  profile: Profile;
  onProfileUpdate: (profile: Profile) => void;
}

export function MyAccountSection({
  profile,
  onProfileUpdate,
}: MyAccountSectionProps) {
  const { isMasterSupportContext } = useAuthStore();

  async function handleProfileSave(payload: ProfileUpdate): Promise<Profile> {
    if (isMasterSupportContext) {
      return updateTenantProfile(payload);
    }
    return updateProfile(payload);
  }

  return (
    <Tabs
      defaultValue="profile"
      orientation="horizontal"
      className="w-full"
    >
      <TabsList variant="line" aria-label={t("frontend.my_account.section_heading")}>
        <TabsTrigger value="profile">
          {t("frontend.my_account.tab_profile")}
        </TabsTrigger>
        {!isMasterSupportContext && (
          <TabsTrigger value="security">
            {t("frontend.my_account.tab_security")}
          </TabsTrigger>
        )}
        <TabsTrigger value="data">
          {t("frontend.my_account.tab_data")}
        </TabsTrigger>
      </TabsList>

      <TabsContent value="profile" className="pt-6">
        <ProfileSection
          profile={profile}
          onProfileUpdate={onProfileUpdate}
          onSave={handleProfileSave}
        />
      </TabsContent>

      {!isMasterSupportContext && (
        <TabsContent value="security" className="pt-6">
          <PasswordSection />
        </TabsContent>
      )}

      <TabsContent value="data" className="pt-6">
        <DataTabContent />
      </TabsContent>
    </Tabs>
  );
}
