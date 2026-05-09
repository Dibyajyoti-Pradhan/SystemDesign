"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { marked } from "marked";
import { Mermaid } from "@/components/Mermaid";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Pause,
  Play,
  StepForward,
  Send,
  Megaphone,
  CheckCircle2,
  AlertTriangle,
  User,
  Bot,
} from "lucide-react";

type AgentRole = "interviewer" | "candidate";
type SteerTarget = "interviewer" | "candidate" | "both";

type Msg =
  | { role: AgentRole; content: string; ts: number }
  | { role: "steer"; content: string; target: SteerTarget; consumed: boolean; ts: number };

interface Props {
  sessionId: number;
  questionTitle: string;
  initialTranscript: Msg[];
  initialEnded: boolean;
}

function MarkdownWithMermaid({ text }: { text: string }) {
  const segments = useMemo(() => {
    const parts: Array<{ kind: "md"; text: string } | { kind: "mermaid"; code: string }> = [];
    const re = /```mermaid\n([\s\S]*?)```/g;
    let last = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      if (m.index > last) parts.push({ kind: "md", text: text.slice(last, m.index) });
      parts.push({ kind: "mermaid", code: m[1] });
      last = re.lastIndex;
    }
    if (last < text.length) parts.push({ kind: "md", text: text.slice(last) });
    return parts;
  }, [text]);

  return (
    <>
      {segments.map((seg, i) =>
        seg.kind === "mermaid" ? (
          <Mermaid key={i} chart={seg.code} />
        ) : (
          <div
            key={i}
            className="prose-system text-sm"
            dangerouslySetInnerHTML={{ __html: marked.parse(seg.text, { async: false }) as string }}
          />
        ),
      )}
    </>
  );
}

function stripSentinel(text: string): string {
  return text.replace(/<<INTERVIEW_END>>/g, "").trimEnd();
}

function MessageBubble({
  role,
  content,
  streaming,
}: {
  role: AgentRole;
  content: string;
  streaming?: boolean;
}) {
  const isInterviewer = role === "interviewer";
  const display = stripSentinel(content);
  return (
    <div className={isInterviewer ? "" : "ml-8"}>
      <div className="flex items-center gap-2 mb-1">
        <Badge variant={isInterviewer ? "default" : "muted"} className="text-[10px] gap-1">
          {isInterviewer ? <Bot className="h-3 w-3" /> : <User className="h-3 w-3" />}
          {isInterviewer ? "Interviewer" : "Candidate"}
        </Badge>
        {streaming && (
          <span className="text-[10px] text-muted-foreground animate-pulse">streaming…</span>
        )}
      </div>
      <Card className={isInterviewer ? "" : "bg-muted/30"}>
        <CardContent className="py-3">
          {display ? <MarkdownWithMermaid text={display} /> : <span className="text-muted-foreground text-sm italic">…</span>}
        </CardContent>
      </Card>
    </div>
  );
}

function SteerNote({ content, target }: { content: string; target: SteerTarget }) {
  return (
    <div className="my-3 px-4 py-2 border-l-2 border-amber-500 bg-amber-500/5 rounded text-xs">
      <div className="flex items-center gap-2 text-amber-700 dark:text-amber-300 font-medium mb-1">
        <Megaphone className="h-3 w-3" />
        Observer steer
        <Badge variant="outline" className="text-[10px]">→ {target}</Badge>
      </div>
      <div className="text-foreground/80">{content}</div>
    </div>
  );
}

export function AiVsAiSession({ sessionId, questionTitle, initialTranscript, initialEnded }: Props) {
  const router = useRouter();
  const [messages, setMessages] = useState<Msg[]>(initialTranscript);
  const [streamingRole, setStreamingRole] = useState<AgentRole | null>(null);
  const [streamingText, setStreamingText] = useState("");
  const [paused, setPaused] = useState(initialEnded);
  const [ended, setEnded] = useState(initialEnded);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [steerText, setSteerText] = useState("");
  const [steerTarget, setSteerTarget] = useState<SteerTarget>("both");
  const [grading, setGrading] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [autoPauseReason, setAutoPauseReason] = useState<null | "interviewer_signed_off" | "hard_cap">(null);

  const END_SENTINEL = "<<INTERVIEW_END>>";

  // Whose turn is next? Used for status indicator.
  const nextAgent: AgentRole = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.role === "interviewer") return "candidate";
      if (m.role === "candidate") return "interviewer";
    }
    return "interviewer";
  }, [messages]);

  const pendingSteers = useMemo(
    () => messages.filter((m): m is Extract<Msg, { role: "steer" }> => m.role === "steer" && !m.consumed),
    [messages],
  );

  // Auto-scroll on stream
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [streamingText, messages.length]);

  const step = useCallback(async () => {
    if (running || ended) return;
    setRunning(true);
    setError(null);

    const ctl = new AbortController();
    abortRef.current = ctl;
    let accumulated = "";
    let role: AgentRole = nextAgent;

    try {
      const res = await fetch("/api/interview/ai-vs-ai/step", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId }),
        signal: ctl.signal,
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`step failed (${res.status}): ${text || "unknown"}`);
      }

      const headerRole = res.headers.get("x-agent-role");
      if (headerRole === "interviewer" || headerRole === "candidate") role = headerRole;

      // If a steer was consumed, mark it consumed locally (server already did).
      const steerConsumed = res.headers.get("x-steer-consumed") === "1";
      const forcedWrap = res.headers.get("x-force-wrap") === "1";

      setStreamingRole(role);
      setStreamingText("");

      if (!res.body) {
        throw new Error("Empty response from server");
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        accumulated += chunk;
        setStreamingText((prev) => prev + chunk);
      }

      if (!accumulated) {
        throw new Error("Empty response from server");
      }
      // If the server embedded a stream-level error sentinel, surface it as an error state.
      if (accumulated.includes("[error:")) {
        const match = accumulated.match(/\[error: ([^\]]+)\]/);
        throw new Error(match ? match[1] : "upstream error (see stream body)");
      }

      // Commit the streamed message into the transcript.
      setMessages((prev) => {
        let updated = prev;
        if (steerConsumed) {
          // Find the most recent unconsumed steer matching this agent or 'both' and mark consumed.
          for (let i = updated.length - 1; i >= 0; i--) {
            const m = updated[i];
            if (
              m.role === "steer" &&
              !m.consumed &&
              (m.target === role || m.target === "both")
            ) {
              updated = updated.map((x, idx) =>
                idx === i && x.role === "steer" ? { ...x, consumed: true } : x,
              );
              break;
            }
          }
        }
        return [...updated, { role, content: accumulated, ts: Date.now() }];
      });

      // Termination detection.
      if (accumulated.includes(END_SENTINEL)) {
        setAutoPauseReason("interviewer_signed_off");
        setPaused(true);
      } else if (forcedWrap) {
        setAutoPauseReason("hard_cap");
        setPaused(true);
      }
    } catch (e: any) {
      if (e?.name !== "AbortError") {
        setError(e?.message ?? String(e));
        setPaused(true);
      }
    } finally {
      setStreamingRole(null);
      setStreamingText("");
      setRunning(false);
      abortRef.current = null;
    }
  }, [nextAgent, running, ended, sessionId]);

  // Auto-step loop: when not paused, not running, not ended → fire next step.
  useEffect(() => {
    if (paused || running || ended) return;
    const id = setTimeout(() => {
      step();
    }, 250); // small delay between turns for readability
    return () => clearTimeout(id);
  }, [paused, running, ended, step, messages.length]);

  const handlePause = () => setPaused(true);
  const handleResume = () => setPaused(false);
  const handleStep = () => {
    if (!running && !ended) step();
  };

  const handleInjectSteer = async () => {
    if (!steerText.trim()) return;
    try {
      const res = await fetch("/api/interview/ai-vs-ai/steer", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId, content: steerText.trim(), target: steerTarget }),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t);
      }
      setMessages((prev) => [
        ...prev,
        { role: "steer", content: steerText.trim(), target: steerTarget, consumed: false, ts: Date.now() },
      ]);
      setSteerText("");
      // Keep paused state as-is. User decides when to resume.
    } catch (e: any) {
      setError(e?.message ?? String(e));
    }
  };

  const handleEnd = async () => {
    if (running) abortRef.current?.abort();
    setPaused(true);
    setEnded(true);
    // Mark all pending steers consumed so the "N steers pending" badge clears immediately.
    setMessages((prev) =>
      prev.map((m) => (m.role === "steer" && !m.consumed ? { ...m, consumed: true } : m)),
    );
    setGrading(true);
    try {
      const res = await fetch("/api/interview/grade", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId }),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t);
      }
    } catch (e: any) {
      setError(`Grading failed: ${e?.message ?? String(e)}`);
    } finally {
      setGrading(false);
      // Always refresh so the server-rendered badge picks up endedAt, even if grading failed.
      router.refresh();
    }
  };

  const turnCount = messages.filter((m) => m.role !== "steer").length;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Bot className="h-4 w-4" /> AI vs AI · {questionTitle}
            </CardTitle>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>turn {turnCount}</span>
              {ended ? (
                <Badge variant="muted" className="gap-1"><CheckCircle2 className="h-3 w-3" />ended</Badge>
              ) : paused ? (
                <Badge variant="outline">paused</Badge>
              ) : running ? (
                <Badge>{streamingRole ?? "…"} thinking</Badge>
              ) : (
                <Badge variant="outline">→ {nextAgent} up</Badge>
              )}
              {pendingSteers.length > 0 && (
                <Badge variant="outline" className="border-amber-500 text-amber-700 dark:text-amber-300">
                  {pendingSteers.length} steer{pendingSteers.length === 1 ? "" : "s"} pending
                </Badge>
              )}
            </div>
          </div>
        </CardHeader>
      </Card>

      <div className="space-y-4">
        {messages.map((m, i) =>
          m.role === "steer" ? (
            <SteerNote key={i} content={m.content} target={m.target} />
          ) : (
            <MessageBubble key={i} role={m.role} content={m.content} />
          ),
        )}
        {streamingRole && (
          <MessageBubble role={streamingRole} content={streamingText} streaming />
        )}
        <div ref={messagesEndRef} />
      </div>

      {error && (
        <Card className="border-destructive/40 bg-destructive/5">
          <CardContent className="py-3 flex items-start gap-2 text-sm">
            <AlertTriangle className="h-4 w-4 text-destructive mt-0.5 shrink-0" />
            <div className="flex-1">
              <div className="font-medium text-destructive">Step failed</div>
              <div className="text-muted-foreground">{error}</div>
            </div>
            {!ended && (
              <Button
                size="sm"
                variant="outline"
                className="shrink-0"
                onClick={() => { setError(null); step(); }}
                disabled={running}
              >
                Retry
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {autoPauseReason && !ended && (
        <Card className="border-emerald-500/40 bg-emerald-500/5">
          <CardContent className="py-4 flex items-start gap-3">
            <CheckCircle2 className="h-5 w-5 text-emerald-600 mt-0.5" />
            <div className="flex-1">
              <div className="font-medium">
                {autoPauseReason === "interviewer_signed_off"
                  ? "Interviewer wrapped up the session."
                  : "Hit the 24-turn hard cap."}
              </div>
              <div className="text-sm text-muted-foreground">
                Grade now to see how the candidate did, or resume to push further.
              </div>
            </div>
            <Button onClick={handleEnd} disabled={grading}>
              {grading ? "Grading…" : "Grade now"}
            </Button>
          </CardContent>
        </Card>
      )}

      {!ended && (
        <Card className="sticky bottom-4 shadow-lg">
          <CardContent className="py-4 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              {paused ? (
                <Button onClick={handleResume} disabled={running}>
                  <Play className="h-4 w-4" /> Resume
                </Button>
              ) : (
                <Button variant="outline" onClick={handlePause} disabled={ended}>
                  <Pause className="h-4 w-4" /> Pause
                </Button>
              )}
              <Button variant="outline" onClick={handleStep} disabled={running || ended}>
                <StepForward className="h-4 w-4" /> Step (1 turn)
              </Button>
              <div className="flex-1" />
              <Button variant="destructive" onClick={handleEnd} disabled={grading || turnCount < 2}>
                {grading ? "Grading…" : "End & grade"}
              </Button>
            </div>

            <div className="border-t pt-3 space-y-2">
              <div className="flex items-center gap-2">
                <Megaphone className="h-4 w-4 text-amber-600" />
                <span className="text-sm font-medium">Steer</span>
                <span className="text-xs text-muted-foreground">applied to next turn of target agent</span>
              </div>
              <textarea
                value={steerText}
                onChange={(e) => setSteerText(e.target.value)}
                placeholder='e.g. "Push harder on partition key choice" or "Propose using Cassandra"'
                rows={2}
                className="w-full p-2 text-sm border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <div className="flex items-center gap-3 text-xs">
                <span className="text-muted-foreground">target:</span>
                {(["interviewer", "candidate", "both"] as const).map((t) => (
                  <label key={t} className="flex items-center gap-1 cursor-pointer">
                    <input
                      type="radio"
                      name="target"
                      checked={steerTarget === t}
                      onChange={() => setSteerTarget(t)}
                      className="cursor-pointer"
                    />
                    <span className="capitalize">{t}</span>
                  </label>
                ))}
                <div className="flex-1" />
                <Button size="sm" onClick={handleInjectSteer} disabled={!steerText.trim()}>
                  <Send className="h-3 w-3" /> Inject
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
