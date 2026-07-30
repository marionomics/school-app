import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "@/lib/auth";
import { Toaster } from "@/components/Toaster";
import Login from "@/pages/Login";
import Onboarding from "@/pages/Onboarding";
import Shell from "@/components/Shell";
import Home from "@/pages/Home";
import Classes from "@/pages/Classes";
import JoinByLink from "@/pages/JoinByLink";
import Thread from "@/pages/Thread";
import Compose from "@/pages/Compose";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  if (!user.username && location.pathname !== "/onboarding")
    return <Navigate to="/onboarding" replace state={{ from: location }} />;
  return <>{children}</>;
}

export default function App() {
  return (
    <AuthProvider>
      <Toaster>
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
                  <Shell>
                    <Home />
                  </Shell>
                </RequireAuth>
              }
            />
            <Route
              path="/clases"
              element={
                <RequireAuth>
                  <Shell>
                    <Classes />
                  </Shell>
                </RequireAuth>
              }
            />
            <Route
              path="/join/:code"
              element={
                <RequireAuth>
                  <JoinByLink />
                </RequireAuth>
              }
            />
            <Route
              path="/post/:id"
              element={
                <RequireAuth>
                  <Shell>
                    <Thread />
                  </Shell>
                </RequireAuth>
              }
            />
            <Route
              path="/componer"
              element={
                <RequireAuth>
                  <Compose />
                </RequireAuth>
              }
            />
          </Routes>
        </BrowserRouter>
      </Toaster>
    </AuthProvider>
  );
}
