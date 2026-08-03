import { useClassSettings } from "@/hooks/useClassSettings";
import SettingsPage from "@/components/SettingsPage";
import { Card } from "@/components/ui/card";
import { es } from "@/strings/es";

/** Read-only for now. The settings endpoint accepts weights, point values and
 *  the attendance minimum — nothing else — so editing name or dates would need
 *  a new backend endpoint, which is outside this pass. Recorded in future.md. */
export default function Clase() {
  const { klass, isPending } = useClassSettings();

  if (isPending || klass == null)
    return (
      <SettingsPage title={es.configurar.groupClase}>
        <p className="text-muted-foreground">{es.common.loading}</p>
      </SettingsPage>
    );

  return (
    <SettingsPage title={es.configurar.groupClase}>
      <Card className="p-4">
        <p className="text-[10px] font-semibold tracking-widest uppercase text-muted-foreground">
          {es.configurar.claseName}
        </p>
        <p className="mt-1 text-sm">{klass.name}</p>
      </Card>

      <Card className="p-4">
        <p className="text-[10px] font-semibold tracking-widest uppercase text-muted-foreground">
          {es.configurar.claseStart}
        </p>
        <p className="mt-1 text-sm tabular-nums">{klass.start_date}</p>
      </Card>

      <Card className="p-4">
        <p className="text-[10px] font-semibold tracking-widest uppercase text-muted-foreground">
          {es.configurar.claseEnd}
        </p>
        <p className="mt-1 text-sm tabular-nums">{klass.end_date}</p>
      </Card>

      <p className="text-xs text-muted-foreground">
        {es.configurar.claseReadOnly}
      </p>
    </SettingsPage>
  );
}
