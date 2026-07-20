import { es } from "@/strings/es";

export default function Home() {
  return (
    <div className="flex flex-col items-center gap-4 p-10 text-center text-muted-foreground">
      <p className="text-4xl">🏗️</p>
      <p>{es.home.feedComingSoon}</p>
    </div>
  );
}
