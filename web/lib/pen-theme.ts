import fs from "fs";
import path from "path";

export type PenDoc = {
  version?: string;
  variables?: Record<string, { type: string; value: string | number }>;
  children?: unknown[];
};

/** Resolved on server from repo layout: web/ sibling to design/done.pen */
export function penFilePath(): string {
  return path.join(process.cwd(), "..", "design", "done.pen");
}

export function readPenDoc(): PenDoc | null {
  const p = penFilePath();
  try {
    const raw = fs.readFileSync(p, "utf8");
    return JSON.parse(raw) as PenDoc;
  } catch {
    return null;
  }
}

export function penVariablesToCssRoot(doc: PenDoc | null): string {
  const variables = doc?.variables;
  if (!variables) {
    return `:root {
      --pen-accent:#58a6ff;--pen-bg:#0d1117;--pen-border:#30363d;--pen-danger:#f85149;
      --pen-success:#3fb950;--pen-surface:#161b22;--pen-text-primary:#e6edf3;--pen-text-secondary:#8b949e;
      --pen-warning:#d29922;--pen-radius-control:2px;--pen-font-ui:"Inter";--pen-font-mono:"IBM Plex Mono";
    }`;
  }
  const lines: string[] = [];
  for (const [name, spec] of Object.entries(variables)) {
    const cssName = `--pen-${name.replace(/_/g, "-")}`;
    if (spec.type === "color") {
      lines.push(`${cssName}:${spec.value};`);
    } else if (spec.type === "string") {
      lines.push(`${cssName}:"${spec.value}";`);
    } else if (spec.type === "number") {
      const suffix =
        name.includes("radius") || name.includes("padding") || name.includes("space")
          ? "px"
          : "";
      lines.push(`${cssName}:${spec.value}${suffix};`);
    }
  }
  return `:root{${lines.join("")}}`;
}

/** Optional: expose raw path + version for debugging in UI */
export function penMeta(): { path: string; version: string | undefined; loaded: boolean } {
  const doc = readPenDoc();
  return {
    path: penFilePath(),
    version: doc?.version,
    loaded: !!doc?.variables,
  };
}
