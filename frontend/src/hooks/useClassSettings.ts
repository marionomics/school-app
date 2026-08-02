import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useToast } from "@/components/Toaster";
import { es } from "@/strings/es";
import type { ClassOut, ClassSettings, MyClasses } from "@/lib/types";

/** The teacher's class and its settings, plus a partial-PATCH saver.
 *
 *  Every settings group page needs exactly this, so it lives here rather than
 *  being copied six times. The class picker for teachers with more than one
 *  class is deliberately not here yet — teaching[0] matches what the rest of
 *  the teacher surfaces already assume. */
export function useClassSettings() {
  const qc = useQueryClient();
  const toast = useToast();

  const mine = useQuery({
    queryKey: ["classes-mine"],
    queryFn: () => api<MyClasses>("/api/classes/mine"),
  });
  const klass: ClassOut | undefined = mine.data?.teaching?.[0];

  const settings = useQuery({
    queryKey: ["settings", klass?.id],
    queryFn: () => api<ClassSettings>(`/api/classes/${klass!.id}/settings`),
    enabled: klass != null,
  });

  const save = useMutation({
    mutationFn: (body: Record<string, number>) =>
      api<ClassSettings>(`/api/classes/${klass!.id}/settings`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: (data) => {
      qc.setQueryData(["settings", klass?.id], data);
      // A weight or a point value changes every grade in the class.
      void qc.invalidateQueries({ queryKey: ["grade"] });
      toast.show(es.configurar.saved);
    },
    onError: () => toast.show(es.configurar.saveError),
  });

  return {
    klass,
    settings: settings.data,
    isPending: mine.isPending || (klass != null && settings.isPending),
    save,
  };
}
