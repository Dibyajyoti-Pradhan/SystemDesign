import Anthropic from "@anthropic-ai/sdk";
import * as cli from "./claude-cli";

// When ANTHROPIC_API_KEY is absent (local dev), delegate to the claude CLI
// so devs can use their Pro/Max subscription without a separate API key.
// In production, ANTHROPIC_API_KEY must be set and the SDK path is always used.
const useCli = () => !process.env.ANTHROPIC_API_KEY;

export class ClaudeCliError extends Error {
  constructor(message: string, public stderr?: string, public exitCode?: number | null) {
    super(message);
    this.name = "ClaudeCliError";
  }
}

// Kept for API compatibility with callers that catch this specifically
export class ClaudeCliNotFoundError extends ClaudeCliError {
  constructor() {
    super("Anthropic API key not configured. Set ANTHROPIC_API_KEY environment variable.");
    this.name = "ClaudeCliNotFoundError";
  }
}

export type ClaudeModel = "sonnet" | "opus" | "haiku" | (string & {});

export interface ClaudeRunOptions {
  prompt: string;
  systemPrompt?: string;
  model?: ClaudeModel;
  jsonSchema?: object;
  cwd?: string;
  signal?: AbortSignal;
  timeoutMs?: number;
  extraArgs?: string[];
  tools?: string;
}

const MODEL_MAP: Record<string, string> = {
  sonnet: "claude-sonnet-4-6",
  opus: "claude-opus-4-7",
  haiku: "claude-haiku-4-5-20251001",
};

function resolveModel(alias?: ClaudeModel): string {
  if (!alias) return MODEL_MAP.sonnet;
  return MODEL_MAP[alias] ?? alias;
}

function getClient(): Anthropic {
  if (!process.env.ANTHROPIC_API_KEY) throw new ClaudeCliNotFoundError();
  return new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
}

export async function claudeRun(opts: ClaudeRunOptions): Promise<string> {
  if (useCli()) return cli.claudeRun(opts);
  const client = getClient();
  const model = resolveModel(opts.model);

  const messages: Anthropic.MessageParam[] = [
    { role: "user", content: opts.prompt },
  ];

  const params: Anthropic.MessageCreateParamsNonStreaming = {
    model,
    max_tokens: 8192,
    messages,
    ...(opts.systemPrompt ? { system: opts.systemPrompt } : {}),
  };

  let response: Anthropic.Message;
  try {
    response = await client.messages.create(params, {
      signal: opts.signal,
      timeout: opts.timeoutMs ?? 300_000,
    });
  } catch (e: any) {
    throw new ClaudeCliError(`Anthropic API error: ${e?.message ?? e}`, undefined, undefined);
  }

  const text = response.content
    .filter((b): b is Anthropic.TextBlock => b.type === "text")
    .map((b) => b.text)
    .join("");

  // If caller expects JSON (jsonSchema), extract JSON from the response
  if (opts.jsonSchema) {
    const match = text.match(/```(?:json)?\s*([\s\S]*?)```/) ?? text.match(/(\{[\s\S]*\}|\[[\s\S]*\])/);
    const raw = match ? (match[1] ?? match[0]).trim() : text.trim();
    try {
      return JSON.stringify(JSON.parse(raw));
    } catch {
      return text;
    }
  }

  return text;
}

export async function* claudeStream(opts: ClaudeRunOptions): AsyncGenerator<string, void, unknown> {
  if (useCli()) { yield* cli.claudeStream(opts); return; }
  const client = getClient();
  const model = resolveModel(opts.model);

  const messages: Anthropic.MessageParam[] = [
    { role: "user", content: opts.prompt },
  ];

  const params: Anthropic.MessageCreateParamsStreaming = {
    model,
    max_tokens: 8192,
    messages,
    stream: true,
    ...(opts.systemPrompt ? { system: opts.systemPrompt } : {}),
  };

  let stream: AsyncIterable<Anthropic.MessageStreamEvent>;
  try {
    stream = await client.messages.create(params, {
      signal: opts.signal,
      timeout: opts.timeoutMs ?? 300_000,
    });
  } catch (e: any) {
    throw new ClaudeCliError(`Anthropic API error: ${e?.message ?? e}`);
  }

  for await (const event of stream) {
    if (
      event.type === "content_block_delta" &&
      event.delta.type === "text_delta"
    ) {
      yield event.delta.text;
    }
  }
}

export interface TranscriptMessage {
  role: "user" | "assistant";
  content: string;
}

export function formatTranscriptAsPrompt(transcript: TranscriptMessage[]): string {
  return transcript
    .map((m) => `<${m.role}>\n${m.content}\n</${m.role}>`)
    .join("\n\n");
}
