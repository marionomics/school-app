import { useState } from "react";
import { useClassSettings } from "@/hooks/useClassSettings";
import SettingsPage from "@/components/SettingsPage";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { es } from "@/strings/es";

/** The one settings page where typing is right: a weight is a number the
 *  teacher already has in mind, not something to discover with a slider. */
export default function Pesos() {
  const { settings, isPending, save } = useClassSettings();
  const [tareas, setTareas] = useState<string | null>(null);
  const [examenes, setExamenes] = useState<string | null>(null);

  if (isPending || settings == null)
    return (
      <SettingsPage title={es.configurar.groupPesos}>
        <p className="text-muted-foreground">{es.common.loading}</p>
      </SettingsPage>
    );

  const t = tareas ?? String(settings.tareas_weight);
  const e = examenes ?? String(settings.examenes_weight);

  return (
    <SettingsPage title={es.configurar.groupPesos}>
      <Card className="p-4">
        <Label htmlFor="w-tareas">{es.configurar.pesosTareas}</Label>
        <Input
          id="w-tareas"
          type="number"
          inputMode="numeric"
          min={0}
          max={100}
          className="mt-2"
          value={t}
          onChange={(ev) => setTareas(ev.target.value)}
        />
      </Card>

      <Card className="p-4">
        <Label htmlFor="w-examenes">{es.configurar.pesosExamenes}</Label>
        <Input
          id="w-examenes"
          type="number"
          inputMode="numeric"
          min={0}
          max={100}
          className="mt-2"
          value={e}
          onChange={(ev) => setExamenes(ev.target.value)}
        />
      </Card>

      {/* Deliberately not a warning. The weights are not supposed to reach 100
          — the gap is filled by uncapped participaciones, likes and extras. */}
      <p className="text-xs text-muted-foreground">{es.configurar.pesosRest}</p>

      <Button
        disabled={save.isPending}
        onClick={() =>
          save.mutate({
            tareas_weight: Number(t),
            examenes_weight: Number(e),
          })
        }
      >
        {es.configurar.save}
      </Button>
    </SettingsPage>
  );
}
