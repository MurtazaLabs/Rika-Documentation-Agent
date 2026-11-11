import Link from "next/link";
import { Compass } from "lucide-react";

import { buttonClasses } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <EmptyState
        icon={<Compass className="h-4 w-4" />}
        title="This page does not exist"
        description="The workspace, conversation or document you followed may have been moved or deleted."
        action={
          <div className="flex flex-wrap items-center justify-center gap-2">
            <Link href="/" className={buttonClasses("primary", "md")}>
              Go to dashboard
            </Link>
            <Link href="/projects" className={buttonClasses("secondary", "md")}>
              Browse projects
            </Link>
          </div>
        }
        className="max-w-lg"
      />
    </div>
  );
}
