import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react';

interface Toast {
  id: number;
  message: string;
}

interface ToastContextValue {
  showToast: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const showToast = useCallback((message: string) => {
    const id = nextId++;
    setToasts(prev => [...prev, { id, message }]);
    const timer = setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
      timers.current.delete(id);
    }, 2500);
    timers.current.set(id, timer);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div
        className="fixed left-0 right-0 flex flex-col items-center gap-2 z-[100] pointer-events-none px-4"
        style={{ bottom: 'calc(5rem + env(safe-area-inset-bottom))' }}
      >
        {toasts.map(t => (
          <div
            key={t.id}
            className="bg-gray-900/95 backdrop-blur text-white text-sm font-medium px-5 py-3 rounded-full shadow-2xl shadow-black/30 animate-toast-in"
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): (message: string) => void {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>');
  return ctx.showToast;
}
