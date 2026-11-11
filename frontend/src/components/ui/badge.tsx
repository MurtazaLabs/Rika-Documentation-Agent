import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type Tone = "neutral" | "copper" | "sage" | "rose" | "gold" | "blue" | "violet";

const TONES: Record<Tone, string> = {
  neutral: "border-line bg-surface-2/80 text-muted",
  copper: "border-copper/25 bg-copper/10 text-copper",
  sage: "border-sage/25 bg-sage/10 text-sage",
  rose: "border-rose/25 bg-rose/10 text-rose",
  gold: "border-gold/25 bg-gold/10 text-gold",
  blue: "border-blue/25 bg-blue/10 text-blue",
  violet: "border-[#c9a0c4]/25 bg-[#c9a0c4]/10 text-[#c9a0c4]",
};

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
  mono?: boolean;
}

export function Badge({
  tone = "neutral",
  mono = false,
  className,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-medium leading-4",
        mono && "font-mono tracking-wide",
        TONES[tone],
        className,
      )}
      {...props}
    />
  );
}
