import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "link";
type Size = "sm" | "md" | "lg" | "icon";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-[linear-gradient(180deg,#efb58c,#d9966a)] text-[#1b120c] shadow-[inset_0_1px_0_rgba(255,255,255,0.35),0_10px_30px_-14px_rgba(224,161,121,0.8)] hover:brightness-[1.06] active:brightness-95",
  secondary:
    "border border-line bg-surface-2/70 text-parchment hover:border-line-strong hover:bg-surface-2",
  ghost: "text-muted hover:bg-surface-2/70 hover:text-parchment",
  danger:
    "border border-rose/30 bg-rose/10 text-rose hover:border-rose/50 hover:bg-rose/15",
  link: "px-0 text-copper underline-offset-4 hover:underline",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 gap-1.5 rounded-lg px-3 text-[12px]",
  md: "h-10 gap-2 rounded-xl px-4 text-[13px]",
  lg: "h-12 gap-2 rounded-xl px-5 text-sm",
  icon: "h-9 w-9 rounded-lg",
};

export function buttonClasses(
  variant: Variant = "secondary",
  size: Size = "md",
  className?: string,
) {
  return cn(
    "inline-flex select-none items-center justify-center whitespace-nowrap font-medium transition-[background,border-color,color,filter,transform] duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-copper/40 focus-visible:ring-offset-2 focus-visible:ring-offset-canvas disabled:pointer-events-none disabled:opacity-50",
    VARIANTS[variant],
    SIZES[size],
    className,
  );
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
}

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  icon,
  className,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={buttonClasses(variant, size, className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : icon}
      {children}
    </button>
  );
}
