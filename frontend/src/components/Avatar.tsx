import type { Author } from "@/lib/types";

export default function Avatar({ author, size = 40 }: { author: Author; size?: number }) {
  const initial = (author.username ?? author.name).charAt(0).toUpperCase();
  return author.avatar_url ? (
    <img
      src={author.avatar_url}
      alt={author.name}
      width={size}
      height={size}
      className="rounded-full object-cover"
      referrerPolicy="no-referrer"
    />
  ) : (
    <div
      className="flex items-center justify-center rounded-full bg-muted font-semibold"
      style={{ width: size, height: size }}
    >
      {initial}
    </div>
  );
}
