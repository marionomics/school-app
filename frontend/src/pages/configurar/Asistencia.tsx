import { useState } from "react";
import { useClassSettings } from "@/hooks/useClassSettings";
import SettingsPage from "@/components/SettingsPage";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { formatPoints } from "@/lib/points";
import { es } from "@/strings/es";

export default function Asistencia() {
  const { settings, isPending, save } = useClassSettings();
  const [draft, setDraft] = useState<number | null>(null);

  if (isPending || settings == null)
    return (
      <SettingsPage title={es.configurar.groupAsistencia}>
        <p className="text-muted-foreground">{es.common.loading}</p>
      </SettingsPage>
    );

  const pct = draft ?? settings.attendance_required_pct;

  return (
    <SettingsPage title={es.configurar.groupAsistencia}>
      <Card className="p-4">
        <Label>{es.configurar.asistenciaMin}</Label>
        <p className="mt-1 text-3xl font-semibold tabular-nums">{pct}%</p>
        <p className="text-xs text-muted-foreground">
          {es.configurar.asistenciaMinHelp}
        </p>
        <Slider
          className="mt-4"
          min={0}
          max={100}
          step={5}
          value={pct}
          onValueChange={(v) => setDraft(Array.isArray(v) ? v[0] : v)}
          onValueCommitted={(v) =>
            save.mutate({
              attendance_required_pct: Array.isArray(v) ? v[0] : v,
            })
          }
        />
      </Card>

      {/* Read-only rows: these are stated facts, not choices. Making "un
          retardo cuenta como falta" configurable would need a new column and a
          grade-engine branch — a feature, not a design change. */}
      <div>
        <p className="mb-1 text-[10px] font-semibold tracking-widest uppercase text-muted-foreground">
          {es.configurar.rulesHeader}
        </p>
        <div className="flex items-center justify-between border-b py-3">
          <span className="text-sm font-medium">{es.configurar.faltaCost}</span>
          <span className="text-sm tabular-nums">−10</span>
        </div>
        <p className="pb-3 text-xs text-muted-foreground">{formatPoints(-10)}</p>
        <div className="flex items-center justify-between py-3">
          <span className="text-sm font-medium">
            {es.configurar.retardoRule}
          </span>
          <span className="text-sm text-muted-foreground">
            {es.configurar.retardoRuleValue}
          </span>
        </div>
      </div>
    </SettingsPage>
  );
}
