import {
  Braces,
  FileCode2,
  FileSpreadsheet,
  FileText,
  File as FileIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import type { Document } from "@/lib/types";

const CODE_EXTENSIONS = new Set([
  "py",
  "pyi",
  "js",
  "mjs",
  "cjs",
  "jsx",
  "ts",
  "tsx",
  "java",
  "kt",
  "kts",
  "swift",
  "go",
  "rs",
  "rb",
  "php",
  "cs",
  "c",
  "h",
  "cc",
  "cpp",
  "cxx",
  "hpp",
  "hh",
  "sql",
  "css",
  "scss",
  "sass",
  "less",
  "sh",
  "bash",
  "zsh",
  "ps1",
  "psm1",
  "vue",
  "svelte",
]);

const DOC_EXTENSIONS = new Set(["pdf", "docx", "pptx", "txt", "md", "markdown", "rst", "log"]);
const SHEET_EXTENSIONS = new Set(["csv", "tsv", "xlsx"]);
const JSON_EXTENSIONS = new Set(["json", "ndjson", "yaml", "yml", "toml"]);

export function FileGlyph({
  document,
  filename,
  className,
}: {
  document?: Pick<Document, "filename" | "file_type">;
  filename?: string;
  className?: string;
}) {
  const name = (document?.filename ?? filename ?? "").toLowerCase();
  const extension = name.includes(".") ? name.split(".").pop() ?? "" : "";
  const fileType = document?.file_type ?? "";

  const common = cn("h-4 w-4 shrink-0", className);

  if (fileType === "code" || CODE_EXTENSIONS.has(extension)) {
    return <FileCode2 className={cn(common, "text-copper")} />;
  }
  if (JSON_EXTENSIONS.has(extension)) {
    return <Braces className={cn(common, "text-gold")} />;
  }
  if (SHEET_EXTENSIONS.has(extension)) {
    return <FileSpreadsheet className={cn(common, "text-sage")} />;
  }
  if (DOC_EXTENSIONS.has(extension) || ["pdf", "docx", "pptx"].includes(fileType)) {
    return <FileText className={cn(common, "text-blue")} />;
  }
  return <FileIcon className={cn(common, "text-faint")} />;
}
