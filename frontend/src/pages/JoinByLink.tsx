import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "@/lib/api";

export default function JoinByLink() {
  const { code } = useParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function join() {
      try {
        await api("/api/classes/join", { method: "POST", body: JSON.stringify({ code }) });
        navigate("/clases", { replace: true });
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          navigate("/clases", { replace: true }); // already in — fine
        } else {
          setError(err instanceof ApiError ? err.message : String(err));
        }
      }
    }
    void join();
  }, [code, navigate]);

  return <div className="p-6 text-center text-muted-foreground">{error ?? "…"}</div>;
}
