"use client";

import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from "react";

interface ToastAction {
  label: string;
  onClick: () => void;
}

interface ToastContextValue {
  showToast: (message: string, action?: ToastAction) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (ctx === null) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return ctx;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);
  const [action, setAction] = useState<ToastAction | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = useCallback((next: string, nextAction?: ToastAction) => {
    setMessage(next);
    setAction(nextAction ?? null);
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    // Actionable toasts (e.g. "Add a key") stay up long enough to click.
    timeoutRef.current = setTimeout(() => setMessage(null), nextAction ? 6000 : 2400);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {message !== null && (
        <div className="fixed bottom-[130px] left-1/2 z-[90] flex -translate-x-1/2 items-center gap-3 border border-l-2 border-border border-l-primary bg-secondary px-[18px] py-3 font-mono text-[13px] text-foreground">
          <span>{message}</span>
          {action && (
            <button
              onClick={() => {
                action.onClick();
                setMessage(null);
              }}
              className="font-mono text-[13px] font-medium text-primary underline-offset-2 hover:underline"
            >
              {action.label}
            </button>
          )}
        </div>
      )}
    </ToastContext.Provider>
  );
}
