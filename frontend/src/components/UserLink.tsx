import { Link } from "react-router-dom";
import Avatar from "@/components/Avatar";
import { cn } from "@/lib/utils";
import type { Author } from "@/lib/types";

type Who = Pick<Author, "username" | "name"> & Partial<Author>;

/** Every username or avatar in the app goes through here (CLAUDE.md): if a
 *  name appears, you can tap it and reach the profile. A user who has not
 *  picked a username yet renders as plain text, never a broken link. */
export default function UserLink({
  user,
  avatar = false,
  size = 40,
  className,
  onClick,
  tabIndex,
  "aria-hidden": ariaHidden,
}: {
  user: Who;
  avatar?: boolean;
  size?: number;
  className?: string;
  onClick?: () => void;
  tabIndex?: number;
  "aria-hidden"?: boolean;
}) {
  const body = avatar ? (
    <Avatar author={user as Author} size={size} />
  ) : (
    <span>@{user.username ?? user.name}</span>
  );
  if (!user.username) return <span className={className}>{body}</span>;
  return (
    <Link
      to={`/u/${user.username}`}
      className={cn("hover:underline", className)}
      // Inside clickable rows (/revisar) the tap opens the profile only.
      onClick={(e) => {
        e.stopPropagation();
        onClick?.();
      }}
      tabIndex={tabIndex}
      aria-hidden={ariaHidden}
    >
      {body}
    </Link>
  );
}
