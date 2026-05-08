"use client";

import { useEffect, useRef, useState } from "react";

let _mermaid: typeof import("mermaid").default | null = null;

async function getMermaid() {
  if (_mermaid) return _mermaid;
  const mod = await import("mermaid");
  _mermaid = mod.default;
  _mermaid.initialize({
    startOnLoad: false,
    theme: "neutral",
    // "loose" enables HTML labels so node text measures correctly when it
    // contains line breaks (\n or <br/>). Input is Claude-generated MDX we
    // control, so XSS via mermaid labels is not a concern.
    securityLevel: "loose",
    flowchart: {
      curve: "basis",
      padding: 16,
      htmlLabels: true,
      useMaxWidth: true,
      nodeSpacing: 40,
      rankSpacing: 50,
    },
    sequence: {
      useMaxWidth: true,
      wrap: true,
    },
    fontFamily: "ui-sans-serif, system-ui, sans-serif",
    fontSize: 14,
  });
  return _mermaid;
}

export function Mermaid({ chart, className }: { chart: string; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [svg, setSvg] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mermaid = await getMermaid();
        const id = `m-${Math.random().toString(36).slice(2, 10)}`;
        const { svg } = await mermaid.render(id, chart.trim());
        if (!cancelled) {
          setSvg(svg);
          setError(null);
        }
      } catch (e: unknown) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to render diagram");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [chart]);

  if (error) {
    return (
      <div className="my-4 p-4 border border-destructive/30 bg-destructive/5 rounded text-sm">
        <div className="font-semibold text-destructive mb-1">Diagram error</div>
        <div className="text-muted-foreground">{error}</div>
        <pre className="mt-2 text-xs overflow-x-auto bg-muted p-2 rounded">{chart}</pre>
      </div>
    );
  }

  return (
    <div ref={ref} className={`mermaid-container my-6 flex justify-center ${className ?? ""}`} dangerouslySetInnerHTML={{ __html: svg }} />
  );
}
