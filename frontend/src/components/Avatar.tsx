import { useState } from "react";
import type { Author } from "@/lib/types";

/** An expired signed link (tab open over an hour) or a dead Google URL falls
 *  back to the initial, never a broken image. */
export default function Avatar({ author, size = 40 }: { author: Author; size?: number }) {
  const [failed, setFailed] = useState<string | null>(null);
  const initial = (author.username ?? author.name).charAt(0).toUpperCase();
  const src = author.avatar_url;
  return src && failed !== src ? (
    <img
      src={src}
      alt={author.name}
      width={size}
      height={size}
      className="rounded-full object-cover"
      style={{ width: size, height: size }}
      referrerPolicy="no-referrer"
      onError={() => setFailed(src)}
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
