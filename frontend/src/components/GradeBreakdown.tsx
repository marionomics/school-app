import {
  RiChat3Line,
  RiCloseCircleLine,
  RiFileTextLine,
  RiPushpinLine,
} from "@remixicon/react";
import { formatPoints } from "@/lib/points";
import { es } from "@/strings/es";
import type { GradeSummary } from "@/lib/types";

/** The rubro rows of one class grade: the block the class panel's student
 *  sheet shows, shared with the profile page. The total is left to the
 *  caller, which places it differently on each surface. */
export default function GradeBreakdown({ grade }: { grade: GradeSummary }) {
  return (
    <dl className="mt-3 space-y-2 text-sm">
      <div className="flex justify-between gap-2">
        <dt className="flex items-center gap-1"><RiPushpinLine className="size-3.5" /> {es.grade.tareas}</dt>
        <dd className="text-right">
          {grade.tareas.evaluated
            ? `${formatPoints(grade.tareas.points)} / ${formatPoints(grade.tareas.weight)}`
            : es.grade.notEvaluated}
        </dd>
      </div>
      <div className="flex justify-between gap-2">
        <dt className="flex items-center gap-1"><RiFileTextLine className="size-3.5" /> {es.grade.examenes}</dt>
        <dd className="text-right">
          {grade.examenes.evaluated
            ? `${formatPoints(grade.examenes.points)} / ${formatPoints(grade.examenes.weight)}`
            : es.grade.notEvaluated}
        </dd>
      </div>
      <div className="flex justify-between gap-2">
        <dt className="flex items-center gap-1"><RiChat3Line className="size-3.5" /> {es.grade.participaciones}</dt>
        <dd className="text-right">{formatPoints(grade.ledger.participaciones)}</dd>
      </div>
      {grade.faltas.count > 0 && (
        <div className="flex justify-between gap-2 text-destructive">
          <dt className="flex items-center gap-1"><RiCloseCircleLine className="size-3.5" /> {es.grade.faltas}</dt>
          <dd className="text-right">−{formatPoints(grade.faltas.points)}</dd>
        </div>
      )}
    </dl>
  );
}
