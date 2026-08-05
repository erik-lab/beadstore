import { useRef, useState } from "react";
import { useProfile } from "../auth/ProfileContext";
import { ApiError } from "../lib/apiClient";
import { resizeImageToAvatar } from "../lib/avatarUpload";
import type { Theme } from "../lib/types";
import { Avatar } from "../components/Avatar";
import { Loading } from "../components/States";

const THEME_OPTIONS: { value: Theme; label: string; description: string }[] = [
  { value: "system", label: "Match device", description: "Follow your browser/OS light or dark setting." },
  { value: "light", label: "Light", description: "Always use the light theme." },
  { value: "dark", label: "Dark", description: "Always use the dark theme." },
];

export function SettingsPage() {
  const { profile, loading, updateProfile } = useProfile();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [savingAvatar, setSavingAvatar] = useState(false);
  const [savingTheme, setSavingTheme] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (loading || !profile) {
    return <Loading />;
  }

  async function handleAvatarFile(file: File) {
    setError(null);
    setSavingAvatar(true);
    try {
      const dataUrl = await resizeImageToAvatar(file);
      await updateProfile({ avatar_data_url: dataUrl });
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : (err as Error).message);
    } finally {
      setSavingAvatar(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function removeAvatar() {
    setError(null);
    setSavingAvatar(true);
    try {
      await updateProfile({ avatar_data_url: null });
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : (err as Error).message);
    } finally {
      setSavingAvatar(false);
    }
  }

  async function changeTheme(theme: Theme) {
    setError(null);
    setSavingTheme(true);
    try {
      await updateProfile({ theme });
    } catch (err) {
      setError(err instanceof ApiError ? String(err.detail) : (err as Error).message);
    } finally {
      setSavingTheme(false);
    }
  }

  return (
    <div>
      <h1>Settings</h1>
      <p className="page-subtitle">Personal preferences for your account — these only affect your own view.</p>

      {error && <div className="alert alert-error">{error}</div>}

      <section className="detail-section">
        <h2>Avatar</h2>
        <div className="form-card">
          <div className="sidebar-account">
            <Avatar avatarDataUrl={profile.avatar_data_url} email={profile.email} size={64} />
            <div className="maintenance-row">
              <button
                className="btn-secondary"
                onClick={() => fileInputRef.current?.click()}
                disabled={savingAvatar}
              >
                {savingAvatar ? "Saving..." : "Upload image"}
              </button>
              {profile.avatar_data_url && (
                <button className="btn-secondary" onClick={removeAvatar} disabled={savingAvatar}>
                  Remove
                </button>
              )}
            </div>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleAvatarFile(file);
            }}
          />
        </div>
      </section>

      <section className="detail-section">
        <h2>Theme</h2>
        <div className="form-card">
          <fieldset disabled={savingTheme}>
            <legend>Appearance</legend>
            {THEME_OPTIONS.map((opt) => (
              <label key={opt.value} className="checkbox-label" style={{ marginBottom: 8 }}>
                <input
                  type="radio"
                  name="theme"
                  value={opt.value}
                  checked={profile.theme === opt.value}
                  onChange={() => changeTheme(opt.value)}
                />
                <span>
                  <strong>{opt.label}</strong> — {opt.description}
                </span>
              </label>
            ))}
          </fieldset>
        </div>
      </section>
    </div>
  );
}
