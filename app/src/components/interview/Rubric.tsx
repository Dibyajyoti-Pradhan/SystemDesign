import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, AlertTriangle } from "lucide-react";

export type RubricData = {
  score: number;
  sections: {
    clarification: number;
    estimation: number;
    high_level: number;
    deep_dive: number;
    tradeoffs: number;
  };
  strengths: string[];
  gaps: string[];
};

const SECTION_LABELS: Record<keyof RubricData["sections"], string> = {
  clarification: "Clarification",
  estimation: "Estimation (BoE)",
  high_level: "High-level design",
  deep_dive: "Deep dives",
  tradeoffs: "Tradeoffs",
};

function scoreColor(score: number): string {
  if (score >= 80) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 60) return "text-amber-600 dark:text-amber-400";
  if (score >= 40) return "text-orange-600 dark:text-orange-400";
  return "text-red-600 dark:text-red-400";
}

function scoreBadge(score: number): "default" | "secondary" | "outline" | "muted" {
  if (score >= 80) return "default";
  if (score >= 60) return "secondary";
  return "muted";
}

export function Rubric({ data }: { data: RubricData }) {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Overall</CardTitle>
            <Badge variant={scoreBadge(data.score)}>{data.score} / 100</Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <Progress value={data.score} className="flex-1" />
            <span className={`text-2xl font-bold tabular-nums ${scoreColor(data.score)}`}>
              {data.score}
            </span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">By section</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {(Object.keys(SECTION_LABELS) as Array<keyof RubricData["sections"]>).map((key) => {
            const v = data.sections?.[key] ?? 0;
            return (
              <div key={key} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{SECTION_LABELS[key]}</span>
                  <span className={`tabular-nums ${scoreColor(v)}`}>{v}</span>
                </div>
                <Progress value={v} />
              </div>
            );
          })}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="border-emerald-500/20">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2 text-emerald-700 dark:text-emerald-400">
              <CheckCircle2 className="h-4 w-4" /> Strengths
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.strengths.length === 0 ? (
              <p className="text-sm text-muted-foreground">None recorded.</p>
            ) : (
              <ul className="space-y-2">
                {data.strengths.map((s, i) => (
                  <li key={i} className="text-sm leading-relaxed flex gap-2">
                    <span className="text-emerald-600 dark:text-emerald-400 mt-0.5">+</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card className="border-amber-500/20">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2 text-amber-700 dark:text-amber-400">
              <AlertTriangle className="h-4 w-4" /> Gaps
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.gaps.length === 0 ? (
              <p className="text-sm text-muted-foreground">None recorded.</p>
            ) : (
              <ul className="space-y-2">
                {data.gaps.map((g, i) => (
                  <li key={i} className="text-sm leading-relaxed flex gap-2">
                    <span className="text-amber-600 dark:text-amber-400 mt-0.5">!</span>
                    <span>{g}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
