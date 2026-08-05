interface AvatarProps {
  avatarDataUrl: string | null | undefined;
  email: string | null | undefined;
  size?: number;
}

export function Avatar({ avatarDataUrl, email, size = 32 }: AvatarProps) {
  const initial = email?.trim()?.[0]?.toUpperCase() ?? "?";
  const style = { width: size, height: size, fontSize: size * 0.45 };

  if (avatarDataUrl) {
    return <img className="avatar" style={style} src={avatarDataUrl} alt="Your avatar" />;
  }
  return (
    <div className="avatar avatar-fallback" style={style}>
      {initial}
    </div>
  );
}
