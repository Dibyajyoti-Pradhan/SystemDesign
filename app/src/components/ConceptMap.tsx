"use client";

import { useMemo, useCallback } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type NodeProps,
  Handle,
  Position,
} from "reactflow";
import "reactflow/dist/style.css";
import { useRouter } from "next/navigation";

export type ConceptMapTopic = {
  id: number;
  slug: string;
  title: string;
  category: string;
  categoryOrder: number;
  topicOrder: number;
  mastery: number;
  track: string;
};

export type ConceptMapLink = {
  fromTopicId: number;
  toTopicId: number;
  relation: string;
};

const CATEGORY_COLORS = [
  "hsl(220 70% 92%)", "hsl(160 60% 90%)", "hsl(40 90% 90%)", "hsl(280 60% 92%)",
  "hsl(0 70% 92%)", "hsl(180 60% 90%)", "hsl(100 50% 90%)", "hsl(330 60% 92%)",
  "hsl(20 70% 92%)",
];

function TopicNode({ data }: NodeProps<{ label: string; bg: string; mastery: number }>) {
  return (
    <div
      className="px-3 py-2 rounded border border-foreground/10 shadow-sm text-xs font-medium hover:scale-105 transition-transform cursor-pointer"
      style={{ background: data.bg, minWidth: 130, maxWidth: 180 }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <div className="leading-tight">{data.label}</div>
      {data.mastery > 0 && (
        <div className="mt-1 h-1 w-full bg-black/10 rounded">
          <div className="h-1 bg-foreground/40 rounded" style={{ width: `${data.mastery}%` }} />
        </div>
      )}
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
}

const nodeTypes = { topic: TopicNode };

export function ConceptMap({
  topics,
  links,
}: {
  topics: ConceptMapTopic[];
  links: ConceptMapLink[];
}) {
  const router = useRouter();

  const { nodes, edges } = useMemo(() => {
    const byCat = new Map<string, ConceptMapTopic[]>();
    for (const t of topics) {
      if (!byCat.has(t.category)) byCat.set(t.category, []);
      byCat.get(t.category)!.push(t);
    }
    const cats = [...byCat.keys()];

    const COLS = Math.ceil(Math.sqrt(cats.length));
    const COL_W = 380;
    const ROW_H = 320;
    const NODE_W = 180;
    const NODE_H = 60;

    const ns: Node[] = [];
    cats.forEach((cat, ci) => {
      const items = byCat.get(cat)!;
      const col = ci % COLS;
      const row = Math.floor(ci / COLS);
      const baseX = col * COL_W;
      const baseY = row * ROW_H;
      items.forEach((t, ti) => {
        const innerCols = 2;
        const ic = ti % innerCols;
        const ir = Math.floor(ti / innerCols);
        ns.push({
          id: String(t.id),
          type: "topic",
          position: { x: baseX + ic * (NODE_W + 12), y: baseY + ir * (NODE_H + 12) },
          data: {
            label: t.title,
            bg: CATEGORY_COLORS[ci % CATEGORY_COLORS.length],
            mastery: t.mastery,
            slug: t.slug,
            track: t.track,
          },
        });
      });
    });

    const es: Edge[] = links.map((l, i) => ({
      id: `e-${i}`,
      source: String(l.fromTopicId),
      target: String(l.toTopicId),
      animated: false,
      style: { stroke: "hsl(0 0% 60%)", strokeWidth: 1 },
    }));

    return { nodes: ns, edges: es };
  }, [topics, links]);

  const onNodeClick = useCallback(
    (_: any, node: Node) => {
      const { slug, track } = node.data as any;
      if (slug && track) router.push(`/${track}/topics/${slug}`);
    },
    [router],
  );

  return (
    <div className="w-full h-[80vh] border rounded-lg bg-muted/20">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        fitView
        proOptions={{ hideAttribution: true }}
        minZoom={0.2}
        maxZoom={1.5}
      >
        <Background gap={24} />
        <Controls position="bottom-right" />
        <MiniMap pannable zoomable />
      </ReactFlow>
    </div>
  );
}
