import { useState } from "react";
import { useClassSettings } from "@/hooks/useClassSettings";
import SettingsPage from "@/components/SettingsPage";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { formatPoints, likeCurvePreview } from "@/lib/points";
import { es } from "@/strings/es";

/** Nobody thinks in exponents, so the curve is offered as three behaviours
 *  and each one states its own consequence. The numbers are computed from the
 *  same maths as the engine — never hardcoded. */
const CURVES = [
  { value: "0.5", label: es.configurar.curvaFuerte },
  { value: "0.75", label: es.configurar.curvaSuave },
  { value: "1", label: es.configurar.curvaLineal },
];

export default function Foro() {
  const { settings, isPending, save } = useClassSettings();
  const [draft, setDraft] = useState<number | null>(null);

  if (isPending || settings == null)
    return (
      <SettingsPage title={es.configurar.groupForo}>
        <p className="text-muted-foreground">{es.common.loading}</p>
      </SettingsPage>
    );

  const likeValue = draft ?? Number(settings.like_value);
  const exponent = String(Number(settings.like_exponent));

  return (
    <SettingsPage title={es.configurar.groupForo}>
      <Card className="p-4">
        <Label>{es.configurar.likeValue}</Label>
        <p className="mt-1 text-3xl font-semibold tabular-nums">
          {likeValue.toFixed(1)}
        </p>
        <p className="text-xs text-muted-foreground">
          {formatPoints(likeValue)}
        </p>
        <Slider
          className="mt-4"
          min={0.5}
          max={5}
          step={0.5}
          value={likeValue}
          onValueChange={(v) => setDraft(Array.isArray(v) ? v[0] : v)}
          onValueCommitted={(v) =>
            save.mutate({ like_value: Array.isArray(v) ? v[0] : v })
          }
        />
      </Card>

      <Card className="p-4">
        <Label>{es.configurar.curvaLabel}</Label>
        <RadioGroup
          className="mt-3"
          value={exponent}
          onValueChange={(v) => save.mutate({ like_exponent: Number(v) })}
        >
          {CURVES.map((c) => (
            <div
              key={c.value}
              className="flex items-start gap-3 border-t py-3 first:border-t-0"
            >
              <RadioGroupItem
                value={c.value}
                id={`curve-${c.value}`}
                className="mt-1"
              />
              <Label
                htmlFor={`curve-${c.value}`}
                className="flex flex-col items-start gap-0.5"
              >
                <span className="text-sm font-medium">{c.label}</span>
                <span className="text-xs text-muted-foreground">
                  {es.configurar.curvaPreview.replace(
                    "{n}",
                    String(likeCurvePreview(Number(c.value))),
                  )}
                </span>
              </Label>
            </div>
          ))}
        </RadioGroup>
        <p className="mt-2 text-xs text-muted-foreground">
          {es.configurar.curvaHelp}
        </p>
      </Card>
    </SettingsPage>
  );
}
