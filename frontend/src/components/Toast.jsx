import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), []);

  const push = useCallback(
    (message, type = 'info') => {
      const id = nextId.current++;
      setToasts((t) => [...t, { id, message, type }]);
      setTimeout(() => dismiss(id), type === 'error' ? 6000 : 4000);
    },
    [dismiss],
  );

  const api = useMemo(
    () => ({
      success: (m) => push(m, 'success'),
      error: (m) => push(m, 'error'),
      info: (m) => push(m, 'info'),
    }),
    [push],
  );

  const Icon = { success: CheckCircle2, error: AlertCircle, info: Info };

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => {
          const I = Icon[t.type];
          return (
            <div key={t.id} className={`toast ${t.type}`}>
              <I size={18} />
              <span>{t.message}</span>
              <button onClick={() => dismiss(t.id)} aria-label="Dismiss notification">
                <X size={16} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside ToastProvider');
  return ctx;
}
