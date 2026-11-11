import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  className,
  children,
}: {
  eyebrow?: string;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <header className={cn("flex flex-col gap-5", className)}>
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div className="min-w-0">
          {eyebrow ? (
            <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.22em] text-copper">
              {eyebrow}
            </p>
          ) : null}
          <h1 className="font-serif text-[2rem] leading-[1.08] tracking-[-0.03em] text-parchment md:text-[2.6rem]">
            {title}
          </h1>
          {description ? (
            <p className="mt-2.5 max-w-2xl text-[13px] leading-relaxed text-muted">
              {description}
            </p>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      {children}
    </header>
  );
}
