"use client";

import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { cn } from "@/lib/utils";

const MenuContext = createContext<{ close: () => void }>({ close: () => {} });

interface MenuProps {
  trigger: ReactNode;
  children: ReactNode;
  label: string;
  align?: "left" | "right";
  className?: string;
}

export function Menu({
  trigger,
  children,
  label,
  align = "right",
  className,
}: MenuProps) {
  const [open, setOpen] = useState(false);
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!container.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className={cn("relative", className)} ref={container}>
      <button
        type="button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-faint transition-colors hover:bg-surface-2 hover:text-parchment focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-copper/40"
      >
        {trigger}
      </button>
      {open ? (
        <MenuContext.Provider value={{ close: () => setOpen(false) }}>
          <div
            role="menu"
            className={cn(
              "absolute top-full z-30 mt-1.5 min-w-48 overflow-hidden rounded-xl border border-line bg-surface p-1 shadow-[0_20px_60px_-15px_rgba(0,0,0,0.85)] animate-[fade-up_120ms_ease-out]",
              align === "right" ? "right-0" : "left-0",
            )}
          >
            {children}
          </div>
        </MenuContext.Provider>
      ) : null}
    </div>
  );
}

interface MenuItemProps {
  children: ReactNode;
  onSelect: () => void;
  icon?: ReactNode;
  danger?: boolean;
  disabled?: boolean;
}

export function MenuItem({
  children,
  onSelect,
  icon,
  danger = false,
  disabled = false,
}: MenuItemProps) {
  const { close } = useContext(MenuContext);
  return (
    <button
      type="button"
      role="menuitem"
      disabled={disabled}
      onClick={() => {
        close();
        onSelect();
      }}
      className={cn(
        "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs transition-colors disabled:pointer-events-none disabled:opacity-40",
        danger
          ? "text-rose hover:bg-rose/10"
          : "text-muted hover:bg-surface-2 hover:text-parchment",
      )}
    >
      {icon ? <span className="text-current">{icon}</span> : null}
      {children}
    </button>
  );
}

export function MenuSeparator() {
  return <div className="my-1 h-px bg-line/70" />;
}
