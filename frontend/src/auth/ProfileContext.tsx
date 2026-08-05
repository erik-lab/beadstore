import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "../lib/apiClient";
import { applyTheme } from "../lib/theme";
import type { Profile } from "../lib/types";
import { useAuth } from "./AuthContext";

interface ProfileContextValue {
  profile: Profile | null;
  loading: boolean;
  updateProfile: (patch: Partial<Pick<Profile, "avatar_data_url" | "theme">>) => Promise<void>;
}

const ProfileContext = createContext<ProfileContextValue | undefined>(undefined);

export function ProfileProvider({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!session) {
      setProfile(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    api
      .get<Profile>("/auth/me")
      .then((result) => {
        if (cancelled) return;
        setProfile(result);
        applyTheme(result.theme);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [session]);

  async function updateProfile(patch: Partial<Pick<Profile, "avatar_data_url" | "theme">>) {
    const updated = await api.patch<Profile>("/auth/me", patch);
    setProfile(updated);
    if (patch.theme) applyTheme(updated.theme);
  }

  return (
    <ProfileContext.Provider value={{ profile, loading, updateProfile }}>{children}</ProfileContext.Provider>
  );
}

export function useProfile(): ProfileContextValue {
  const ctx = useContext(ProfileContext);
  if (!ctx) {
    throw new Error("useProfile must be used within a ProfileProvider");
  }
  return ctx;
}
