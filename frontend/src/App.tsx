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
import Revisar from "@/pages/Revisar";
import ConfigurarIndex from "@/pages/configurar/Index";
import Pesos from "@/pages/configurar/Pesos";
import Foro from "@/pages/configurar/Foro";
import Extras from "@/pages/configurar/Extras";
import Asistencia from "@/pages/configurar/Asistencia";
import Salvando from "@/pages/configurar/Salvando";
import Clase from "@/pages/configurar/Clase";
import ClassPanel from "@/pages/ClassPanel";
import PasarLista from "@/pages/PasarLista";

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
            <Route
              path="/revisar"
              element={
                <RequireAuth>
                  <Shell>
                    <Revisar />
                  </Shell>
                </RequireAuth>
              }
            />
            <Route
              path="/configurar"
              element={
                <RequireAuth>
                  <Shell>
                    <ConfigurarIndex />
                  </Shell>
                </RequireAuth>
              }
            />
            <Route
              path="/configurar/pesos"
              element={
                <RequireAuth>
                  <Shell>
                    <Pesos />
                  </Shell>
                </RequireAuth>
              }
            />
            <Route
              path="/configurar/foro"
              element={
                <RequireAuth>
                  <Shell>
                    <Foro />
                  </Shell>
                </RequireAuth>
              }
            />
            <Route
              path="/configurar/extras"
              element={
                <RequireAuth>
                  <Shell>
                    <Extras />
                  </Shell>
                </RequireAuth>
              }
            />
            <Route
              path="/configurar/asistencia"
              element={
                <RequireAuth>
                  <Shell>
                    <Asistencia />
                  </Shell>
                </RequireAuth>
              }
            />
            <Route
              path="/configurar/salvando"
              element={
                <RequireAuth>
                  <Shell>
                    <Salvando />
                  </Shell>
                </RequireAuth>
              }
            />
            <Route
              path="/configurar/clase"
              element={
                <RequireAuth>
                  <Shell>
                    <Clase />
                  </Shell>
                </RequireAuth>
              }
            />
            <Route
              path="/clases/:id"
              element={
                <RequireAuth>
                  <Shell>
                    <ClassPanel />
                  </Shell>
                </RequireAuth>
              }
            />
            <Route
              path="/pasar-lista/:class_id/:session_id"
              element={
                <RequireAuth>
                  <PasarLista />
                </RequireAuth>
              }
            />
          </Routes>
        </BrowserRouter>
      </Toaster>
    </AuthProvider>
  );
}
