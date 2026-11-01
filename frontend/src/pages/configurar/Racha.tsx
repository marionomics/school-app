import { useState } from "react";
import { useClassSettings } from "@/hooks/useClassSettings";
import SettingsPage from "@/components/SettingsPage";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { es } from "@/strings/es";
import type { StreakLevel } from "@/lib/types";

/** Inputs are strings while typing; the API wants fractions, the teacher
 *  thinks in percents. Rounding to integer percents keeps 0.07 from
 *  becoming 7.000000000000001. */
interface Row {
  from: string;
  x2: string;
  x3: string;
}

const toRow = (l: StreakLevel): Row => ({
  from: String(l.from_days),
  x2: String(Math.round(l.x2 * 100)),
  x3: String(Math.round(l.x3 * 100)),
});

const toLevel = (r: Row): StreakLevel => ({
  from_days: Number(r.from),
  x2: Number(r.x2) / 100,
  x3: Number(r.x3) / 100,
});

const isInt = (s: string) => /^\d+$/.test(s.trim());

function rowsValid(rows: Row[]): boolean {
  let prev = 0;
  for (const r of rows) {
    if (!isInt(r.from) || !isInt(r.x2) || !isInt(r.x3)) return false;
    const from = Number(r.from);
    if (from < 1 || from <= prev) return false;
    if (Number(r.x2) + Number(r.x3) > 100) return false;
    prev = from;
  }
  return rows.length <= 8;
}

export default function Racha() {
  const { settings, isPending, save } = useClassSettings();
  const [draft, setDraft] = useState<Row[] | null>(null);

  if (isPending || settings == null)
    return (
      <SettingsPage title={es.configurar.groupRacha}>
        <p className="text-muted-foreground">{es.common.loading}</p>
      </SettingsPage>
    );

  const rows = draft ?? settings.streak_levels.map(toRow);
  const valid = rowsValid(rows);

  const patch = (i: number, key: keyof Row, value: string) =>
    setDraft(rows.map((r, j) => (j === i ? { ...r, [key]: value } : r)));

  const add = () => {
    const last = rows.length ? Number(rows[rows.length - 1].from) : 0;
    const next = Number.isFinite(last) ? last + 7 : 7;
    setDraft([...rows, { from: String(next), x2: "0", x3: "0" }]);
  };

  return (
    <SettingsPage title={es.configurar.groupRacha}>
      <Card className="p-4">
        <p className="text-xs text-muted-foreground">
          {es.configurar.rachaHelp}
        </p>
      </Card>

      {rows.map((r, i) => (
        <Card key={i} className="gap-3 p-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`racha-from-${i}`}>
              {es.configurar.rachaFrom}
            </Label>
            <Input
              id={`racha-from-${i}`}
              type="number"
              inputMode="numeric"
              min={1}
              step={1}
              value={r.from}
              onChange={(e) => patch(i, "from", e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`racha-x2-${i}`}>{es.configurar.racha2x}</Label>
            <Input
              id={`racha-x2-${i}`}
              type="number"
              inputMode="numeric"
              min={0}
              max={100}
              step={1}
              value={r.x2}
              onChange={(e) => patch(i, "x2", e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`racha-x3-${i}`}>{es.configurar.racha3x}</Label>
            <Input
              id={`racha-x3-${i}`}
              type="number"
              inputMode="numeric"
              min={0}
              max={100}
              step={1}
              value={r.x3}
              onChange={(e) => patch(i, "x3", e.target.value)}
            />
          </div>
          <Button
            variant="outline"
            onClick={() => setDraft(rows.filter((_, j) => j !== i))}
          >
            {es.configurar.rachaRemove}
          </Button>
        </Card>
      ))}

      <Button variant="outline" onClick={add} disabled={rows.length >= 8}>
        {es.configurar.rachaAdd}
      </Button>

      {!valid && (
        <p className="text-xs text-destructive">{es.configurar.rachaInvalid}</p>
      )}
      <Button
        disabled={!valid || draft == null || save.isPending}
        onClick={() =>
          save.mutate(
            { streak_levels: rows.map(toLevel) },
            { onSuccess: () => setDraft(null) },
          )
        }
      >
        {es.configurar.save}
      </Button>
    </SettingsPage>
  );
}
