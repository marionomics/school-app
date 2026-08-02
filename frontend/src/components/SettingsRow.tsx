import { Link } from "react-router-dom";
import { RiArrowRightSLine } from "@remixicon/react";

/** One row of the settings index: never editable, always a way in. */
export default function SettingsRow({
  icon,
  name,
  summary,
  to,
}: {
  icon: React.ReactNode;
  name: string;
  summary: string;
  to: string;
}) {
  return (
    <Link
      to={to}
      className="flex items-center gap-3 border-b px-1 py-3 last:border-b-0"
    >
      <span className="flex size-8 shrink-0 items-center justify-center bg-muted text-muted-foreground">
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold">{name}</span>
        <span className="block truncate text-xs text-muted-foreground">
          {summary}
        </span>
      </span>
      <RiArrowRightSLine className="size-4 text-muted-foreground" />
    </Link>
  );
}
