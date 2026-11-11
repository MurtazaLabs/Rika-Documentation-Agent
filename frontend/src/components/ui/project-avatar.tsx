import { cn, initials, projectColor } from "@/lib/utils";

export function ProjectAvatar({
  name,
  size = "md",
  active = false,
  className,
}: {
  name: string;
  size?: "sm" | "md" | "lg";
  active?: boolean;
  className?: string;
}) {
  const sizes = {
    sm: "h-6 w-6 rounded-md text-[9px]",
    md: "h-9 w-9 rounded-lg text-[11px]",
    lg: "h-12 w-12 rounded-xl text-sm",
  };

  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center border font-mono font-medium tracking-wide",
        sizes[size],
        projectColor(name),
        active && "ring-2 ring-copper/30 ring-offset-2 ring-offset-canvas",
        className,
      )}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  );
}
