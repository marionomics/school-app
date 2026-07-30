import { createContext, useCallback, useContext, useState } from "react";

const ToastContext = createContext<{ show: (msg: string) => void }>({ show: () => {} });

export function Toaster({ children }: { children: React.ReactNode }) {
  const [msg, setMsg] = useState<string | null>(null);
  const show = useCallback((m: string) => {
    setMsg(m);
    setTimeout(() => setMsg(null), 3000);
  }, []);
  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      {msg && (
        <div className="fixed bottom-20 left-1/2 z-50 -translate-x-1/2 rounded-full bg-foreground px-4 py-2 text-sm text-background shadow-lg">
          {msg}
        </div>
      )}
    </ToastContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components -- co-locates the toast hook with its provider/context; splitting into a separate file would fragment a small, cohesive module
export const useToast = () => useContext(ToastContext);
