import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export type AppConfig = { file_uploads_enabled: boolean };

/**
 * `/api/config` only changes when the service restarts with different R2
 * variables, so it never goes stale inside a session.
 */
export function useUploadsEnabled(): boolean {
  const q = useQuery({
    queryKey: ["config"],
    queryFn: () => api<AppConfig>("/api/config"),
    staleTime: Infinity,
  });
  return q.data?.file_uploads_enabled ?? false;
}
