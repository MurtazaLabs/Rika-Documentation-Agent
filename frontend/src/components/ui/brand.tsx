import { cn } from "@/lib/utils";

export function RikaMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 40 40"
      fill="none"
      aria-hidden="true"
      className={cn("h-9 w-9", className)}
    >
      <defs>
        <linearGradient id="rika-mark" x1="6" y1="4" x2="34" y2="36">
          <stop stopColor="#f3c19d" />
          <stop offset="0.55" stopColor="#e0a179" />
          <stop offset="1" stopColor="#b8734c" />
        </linearGradient>
      </defs>
      <circle cx="20" cy="20" r="16.5" stroke="url(#rika-mark)" strokeWidth="1.4" />
      <path
        d="M20 3.5c8.2 0 14.5 7.4 14.5 16.5S28.2 36.5 20 36.5"
        stroke="url(#rika-mark)"
        strokeWidth="1.4"
        strokeLinecap="round"
        opacity="0.5"
      />
      <path
        d="M20 10.5c4.4 2.3 7 6.1 7 9.5s-2.6 7.2-7 9.5c-4.4-2.3-7-6.1-7-9.5s2.6-7.2 7-9.5Z"
        stroke="url(#rika-mark)"
        strokeWidth="1.3"
        strokeLinejoin="round"
      />
      <circle cx="20" cy="20" r="2.4" fill="url(#rika-mark)" />
    </svg>
  );
}

export function RikaWordmark({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <RikaMark />
      <div className="leading-none">
        <p className="font-serif text-[25px] tracking-[-0.035em] text-parchment">
          Rika
        </p>
        {!compact ? (
          <p className="mt-1 font-mono text-[8px] uppercase tracking-[0.28em] text-faint">
            project intelligence
          </p>
        ) : null}
      </div>
    </div>
  );
}
