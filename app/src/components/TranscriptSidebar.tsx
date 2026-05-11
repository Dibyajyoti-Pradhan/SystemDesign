"use client";

import { useEffect, useRef } from "react";
import { Loader2, Copy, CheckCircle2 } from "lucide-react";
import { useState } from "react";

export interface TranscriptMessage {
  role: "interviewer" | "candidate";
  content: string;
  timestamp: Date;
}

export interface ScoreObject {
  communication: number;
  correctness: number;
  efficiency: number;
  summary: string;
}

interface TranscriptSidebarProps {
  messages: TranscriptMessage[];
  score?: ScoreObject;
  isStreaming?: boolean;
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between items-center text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-semibold tabular-nums">{value}/5</span>
      </div>
      <div className="h-1.5 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-primary transition-all duration-500"
          style={{ width: `${(value / 5) * 100}%` }}
        />
      </div>
    </div>
  );
}

function formatTime(d: Date): string {
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function TranscriptSidebar({ messages, score, isStreaming = false }: TranscriptSidebarProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = useState(false);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages.length, isStreaming]);

  function copyTranscript() {
    const text = messages
      .map((m) => `[${m.role.toUpperCase()}] ${m.content}`)
      .join("\n\n");
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="flex flex-col h-full border-l bg-background">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">Transcript</span>
          {isStreaming && (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" /> streaming
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={copyTranscript}
          disabled={messages.length === 0}
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-40 transition-colors"
          title="Copy transcript"
        >
          {copied ? (
            <><CheckCircle2 className="h-3.5 w-3.5" /> Copied</>
          ) : (
            <><Copy className="h-3.5 w-3.5" /> Copy</>
          )}
        </button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0">
        {messages.length === 0 && !isStreaming && (
          <p className="text-sm text-muted-foreground text-center py-8">
            The conversation will appear here.
          </p>
        )}
        {messages.map((msg, i) => {
          const isInterviewer = msg.role === "interviewer";
          return (
            <div
              key={i}
              className={`flex flex-col gap-1 ${isInterviewer ? "items-start" : "items-end"}`}
            >
              <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                <span className="uppercase tracking-wide font-medium">
                  {isInterviewer ? "Interviewer" : "You"}
                </span>
                <span>{formatTime(msg.timestamp)}</span>
              </div>
              <div
                className={`max-w-[90%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap leading-relaxed ${
                  isInterviewer
                    ? "bg-muted text-foreground rounded-tl-sm"
                    : "bg-primary text-primary-foreground rounded-tr-sm"
                }`}
              >
                {msg.content}
              </div>
            </div>
          );
        })}
        {isStreaming && messages.length > 0 && messages[messages.length - 1].role === "interviewer" && (
          <div className="flex flex-col items-start gap-1">
            <div className="text-[10px] text-muted-foreground uppercase tracking-wide font-medium">
              Interviewer
            </div>
            <div className="bg-muted rounded-lg rounded-tl-sm px-3 py-2">
              <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
            </div>
          </div>
        )}
      </div>

      {/* Score card */}
      {score && (
        <div className="shrink-0 border-t p-4 space-y-3 bg-muted/20">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Session Score
          </div>
          <div className="space-y-2">
            <ScoreBar label="Communication" value={score.communication} />
            <ScoreBar label="Correctness" value={score.correctness} />
            <ScoreBar label="Efficiency" value={score.efficiency} />
          </div>
          {score.summary && (
            <p className="text-xs text-muted-foreground leading-relaxed border-t pt-2">
              {score.summary}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
