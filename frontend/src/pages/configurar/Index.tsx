import { useQuery } from "@tanstack/react-query";
import { Navigate } from "react-router-dom";
import {
  RiScales3Line,
  RiHeartLine,
  RiSparkling2Line,
  RiCheckboxCircleLine,
  RiFlashlightLine,
  RiEditLine,
} from "@remixicon/react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useClassSettings } from "@/hooks/useClassSettings";
import SettingsRow from "@/components/SettingsRow";
import { es } from "@/strings/es";
import type { Incentive } from "@/lib/types";

/** The index never edits anything. It exists so that opening Configuración
 *  does not confront you with every decision in the app at once. */
export default function ConfigurarIndex() {
  const { user } = useAuth();
  const { klass, settings, isPending } = useClassSettings();

  const incentives = useQuery({
    queryKey: ["class-incentives", klass?.id],
    queryFn: () =>
      api<{ incentives: Incentive[] }>(`/api/classes/${klass!.id}/incentives`),
    select: (d) => d.incentives,
    enabled: klass != null,
  });

  if (user?.role !== "teacher") return <Navigate to="/" replace />;
  if (isPending)
    return <p className="p-4 text-muted-foreground">{es.common.loading}</p>;
  if (klass == null)
    return <p className="p-4 text-muted-foreground">{es.configurar.empty}</p>;

  const curva =
    settings == null
      ? "—"
      : Number(settings.like_exponent) >= 1
        ? es.configurar.curvaLineal
        : Number(settings.like_exponent) >= 0.75
          ? es.configurar.curvaSuave
          : es.configurar.curvaFuerte;

  return (
    <main className="mx-auto max-w-md p-4">
      <h1 className="mb-3 text-sm font-semibold tracking-widest uppercase">
        {es.configurar.title}
      </h1>

      <SettingsRow
        icon={<RiScales3Line className="size-4" />}
        name={es.configurar.groupPesos}
        summary={
          settings
            ? es.configurar.summaryPesos
                .replace("{t}", String(settings.tareas_weight))
                .replace("{e}", String(settings.examenes_weight))
            : "—"
        }
        to="/configurar/pesos"
      />
      <SettingsRow
        icon={<RiHeartLine className="size-4" />}
        name={es.configurar.groupForo}
        summary={
          settings
            ? es.configurar.summaryForo
                .replace("{v}", String(settings.like_value))
                .replace("{c}", curva.toLowerCase())
            : "—"
        }
        to="/configurar/foro"
      />
      <SettingsRow
        icon={<RiSparkling2Line className="size-4" />}
        name={es.configurar.groupExtras}
        summary={es.configurar.summaryExtras.replace(
          "{n}",
          String(incentives.data?.length ?? 0),
        )}
        to="/configurar/extras"
      />
      <SettingsRow
        icon={<RiCheckboxCircleLine className="size-4" />}
        name={es.configurar.groupAsistencia}
        summary={
          settings
            ? es.configurar.summaryAsistencia.replace(
                "{p}",
                String(settings.attendance_required_pct),
              )
            : "—"
        }
        to="/configurar/asistencia"
      />
      <SettingsRow
        icon={<RiFlashlightLine className="size-4" />}
        name={es.configurar.groupSalvando}
        summary={es.configurar.summarySalvando}
        to="/configurar/salvando"
      />
      <SettingsRow
        icon={<RiEditLine className="size-4" />}
        name={es.configurar.groupClase}
        summary={klass.name}
        to="/configurar/clase"
      />
    </main>
  );
}
