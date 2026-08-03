import SettingsPage from "@/components/SettingsPage";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { es } from "@/strings/es";

/** The slot exists so the protocol has a home and an explanation. The mechanic
 *  itself — multipliers, retroactive or forward, how randomness works — touches
 *  the grade engine and needs its own spec and tests. */
export default function Salvando() {
  return (
    <SettingsPage title={es.configurar.salvandoTitle}>
      <Card className="p-4">
        <p className="text-sm">{es.configurar.salvandoBody}</p>
        <Button disabled className="mt-4 w-full">
          {es.configurar.salvandoSoon}
        </Button>
      </Card>
    </SettingsPage>
  );
}
