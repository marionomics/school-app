import { Link } from "react-router-dom";
import { RiArrowLeftSLine } from "@remixicon/react";
import { es } from "@/strings/es";

/** A settings group page: one title, a way back, and one control per line. */
export default function SettingsPage({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <main className="mx-auto max-w-md p-4">
      <Link
        to="/configurar"
        className="mb-3 inline-flex items-center gap-1 text-xs text-muted-foreground"
      >
        <RiArrowLeftSLine className="size-4" /> {es.configurar.back}
      </Link>
      <h1 className="mb-4 text-sm font-semibold tracking-widest uppercase">
        {title}
      </h1>
      <div className="flex flex-col gap-3">{children}</div>
    </main>
  );
}
