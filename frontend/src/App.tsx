import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "@/lib/auth";
import Login from "@/pages/Login";
import Onboarding from "@/pages/Onboarding";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  if (!user.username && location.pathname !== "/onboarding")
    return <Navigate to="/onboarding" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/onboarding"
            element={
              <RequireAuth>
                <Onboarding />
              </RequireAuth>
            }
          />
          <Route
            path="/"
            element={
              <RequireAuth>
                <div className="p-6">home placeholder — Task 10</div>
              </RequireAuth>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
