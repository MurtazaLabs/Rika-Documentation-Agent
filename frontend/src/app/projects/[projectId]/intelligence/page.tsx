"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import {
  Brain,
  FileDiff,
  Layers,
  Route,
  ScanSearch,
  ShieldAlert,
} from "lucide-react";

import { ArchitecturePanel } from "@/components/intelligence/architecture-panel";
import { DocsPanel } from "@/components/intelligence/docs-panel";
import { EndpointsPanel } from "@/components/intelligence/endpoints-panel";
import { FindingsPanel } from "@/components/intelligence/findings-panel";
import { OverviewPanel } from "@/components/intelligence/overview-panel";
import { SymbolsPanel } from "@/components/intelligence/symbols-panel";
import { cn } from "@/lib/utils";

const SECTIONS = [
  {
    id: "overview",
    label: "Overview",
    icon: Brain,
    description: "What this project is made of, and what it depends on.",
  },
  {
    id: "architecture",
    label: "Architecture",
    icon: Layers,
    description: "Layers, their imports, the data model and request flows.",
  },
  {
    id: "endpoints",
    label: "Endpoints",
    icon: Route,
    description: "HTTP routes discovered from the source.",
  },
  {
    id: "code",
    label: "Code",
    icon: ScanSearch,
    description: "Search symbols and read an explanation of each one.",
  },
  {
    id: "docs",
    label: "Documentation",
    icon: FileDiff,
    description: "Where the docs and the implementation disagree.",
  },
  {
    id: "findings",
    label: "Findings",
    icon: ShieldAlert,
    description: "Confirmed defects and issues a human should check.",
  },
] as const;

type SectionId = (typeof SECTIONS)[number]["id"];

export default function IntelligencePage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const [sectionId, setSectionId] = useState<SectionId>("overview");
  const section = SECTIONS.find((item) => item.id === sectionId) ?? SECTIONS[0];

  return (
    <div className="space-y-5">
      <div>
        <h2 className="font-serif text-2xl tracking-[-0.02em] text-parchment">
          Project intelligence
        </h2>
        <p className="mt-1 max-w-3xl text-[12px] leading-relaxed text-muted">
          Analyses derived from the stored index: symbols, imports, chunks and
          documentation. Nothing here calls a model, so every statement can be
          traced back to a file and line.
        </p>
      </div>

      <nav
        aria-label="Intelligence sections"
        className="scrollbar-none -mx-1 flex gap-1 overflow-x-auto pb-1"
      >
        {SECTIONS.map((item) => {
          const Icon = item.icon;
          const active = item.id === section.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setSectionId(item.id)}
              aria-current={active ? "page" : undefined}
              className={cn(
                "inline-flex shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[11.5px] transition-colors",
                active
                  ? "border-copper/35 bg-copper/10 text-copper"
                  : "border-line text-muted hover:border-line-strong hover:text-parchment",
              )}
            >
              <Icon className="h-3.5 w-3.5" strokeWidth={1.7} />
              {item.label}
            </button>
          );
        })}
      </nav>

      <p className="text-[11px] text-faint">{section.description}</p>

      {section.id === "overview" ? <OverviewPanel projectId={projectId} /> : null}
      {section.id === "architecture" ? (
        <ArchitecturePanel projectId={projectId} />
      ) : null}
      {section.id === "endpoints" ? (
        <EndpointsPanel projectId={projectId} />
      ) : null}
      {section.id === "code" ? <SymbolsPanel projectId={projectId} /> : null}
      {section.id === "docs" ? <DocsPanel projectId={projectId} /> : null}
      {section.id === "findings" ? (
        <FindingsPanel projectId={projectId} />
      ) : null}
    </div>
  );
}
