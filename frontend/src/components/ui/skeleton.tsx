import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-lg bg-[linear-gradient(90deg,rgba(255,255,255,0.035),rgba(255,255,255,0.07),rgba(255,255,255,0.035))] bg-[length:200%_100%]",
        className,
      )}
    />
  );
}

export function CardSkeleton() {
  return (
    <div className="rounded-2xl border border-line bg-surface/60 p-5">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="mt-3 h-3 w-2/3" />
      <Skeleton className="mt-6 h-8 w-24" />
    </div>
  );
}
