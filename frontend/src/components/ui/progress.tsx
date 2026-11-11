import { cn } from "@/lib/utils";

export function ProgressBar({
  value,
  tone = "copper",
  className,
}: {
  value: number;
  tone?: "copper" | "sage" | "rose" | "gold";
  className?: string;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  const colors = {
    copper: "bg-copper",
    sage: "bg-sage",
    rose: "bg-rose",
    gold: "bg-gold",
  };

  return (
    <div
      className={cn("h-1 overflow-hidden rounded-full bg-surface-2", className)}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped)}
    >
      <div
        className={cn("h-full rounded-full transition-[width] duration-500", colors[tone])}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
