import { Navigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";

/** /perfil predates profile pages; it now lands on your own. */
export default function Perfil() {
  const { user } = useAuth();
  return user?.username ? <Navigate to={`/u/${user.username}`} replace /> : <Navigate to="/onboarding" replace />;
}
