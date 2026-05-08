import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";

export class ClaudeCliError extends Error {
  constructor(message: string, public stderr?: string, public exitCode?: number | null) {
    super(message);
    this.name = "ClaudeCliError";
  }
}

export class ClaudeCliNotFoundError extends ClaudeCliError {
  constructor() {
    super(
      "`claude` CLI not found in PATH. Install Claude Code from https://docs.anthropic.com/en/docs/claude-code, then run `claude login`. Subscription auth (Pro/Max) is preferred; an ANTHROPIC_API_KEY env var also works.",
    );
    this.name = "ClaudeCliNotFoundError";
  }
}

export type ClaudeModel = "sonnet" | "opus" | "haiku" | (string & {});

export interface ClaudeRunOptions {
  /** The user prompt. Sent via stdin so it's not bound by argv length. */
  prompt: string;
  /** Replaces Claude Code's default system prompt entirely. */
  systemPrompt?: string;
  /** Model alias or full id. Defaults to "sonnet". */
  model?: ClaudeModel;
  /**
   * Enforce structured output. When provided, Claude is constrained to return
   * JSON matching this JSON Schema (passed via --json-schema). Use this for
   * generation tasks where you'll JSON.parse() the result.
   */
  jsonSchema?: object;
  /** Override cwd for the subprocess. Defaults to process.cwd(). */
  cwd?: string;
  /** Abort signal to terminate an in-flight call. */
  signal?: AbortSignal;
  /** Maximum wall time in ms before SIGTERM. Default 5 min. */
  timeoutMs?: number;
  /** Pass extra args (escape hatch). */
  extraArgs?: string[];
  /**
   * Comma-separated list of built-in tools to allow (e.g. "WebSearch,WebFetch").
   * Defaults to "" (no tools). Use this only for the assistant-style routes that
   * need web access — never enable Bash/Edit/Write for user-facing chat.
   */
  tools?: string;
}

const BASE_ARGS = [
  "-p",
  // Skip user/project/local settings — keeps spawned sessions deterministic
  // and lets Claude Code's default agent harness be cached across calls.
  "--setting-sources",
  "",
  // Don't write these throwaway sessions into the user's ~/.claude history.
  "--no-session-persistence",
];

function buildArgs(opts: ClaudeRunOptions, format: "json" | "stream-json" | "text"): string[] {
  const args = [...BASE_ARGS];
  args.push("--tools", opts.tools ?? "");
  args.push("--model", opts.model ?? "sonnet");
  args.push("--output-format", format);
  if (opts.systemPrompt) args.push("--system-prompt", opts.systemPrompt);
  if (opts.jsonSchema) args.push("--json-schema", JSON.stringify(opts.jsonSchema));
  if (format === "stream-json") {
    args.push("--verbose"); // stream-json requires verbose on Claude Code
    args.push("--include-partial-messages");
  }
  if (opts.extraArgs) args.push(...opts.extraArgs);
  return args;
}

function spawnClaude(args: string[], cwd?: string): ChildProcessWithoutNullStreams {
  try {
    return spawn("claude", args, {
      cwd: cwd ?? process.cwd(),
      env: process.env,
      stdio: ["pipe", "pipe", "pipe"],
    });
  } catch (e: any) {
    if (e?.code === "ENOENT") throw new ClaudeCliNotFoundError();
    throw e;
  }
}

/**
 * One-shot text generation. Returns the full response text.
 *
 * @example
 *   const text = await claudeRun({
 *     systemPrompt: "Output only valid Mermaid.",
 *     prompt: "Draw a load balancer in front of 3 app servers.",
 *   });
 */
export async function claudeRun(opts: ClaudeRunOptions): Promise<string> {
  const args = buildArgs(opts, "json");
  const proc = spawnClaude(args, opts.cwd);

  const onAbort = () => proc.kill("SIGTERM");
  if (opts.signal) {
    if (opts.signal.aborted) {
      proc.kill("SIGKILL");
      throw new ClaudeCliError("aborted before start");
    }
    opts.signal.addEventListener("abort", onAbort, { once: true });
  }

  const timeout = setTimeout(() => proc.kill("SIGTERM"), opts.timeoutMs ?? 300_000);

  let stdout = "";
  let stderr = "";
  proc.stdout.setEncoding("utf8");
  proc.stderr.setEncoding("utf8");
  proc.stdout.on("data", (c: string) => (stdout += c));
  proc.stderr.on("data", (c: string) => (stderr += c));

  // Write the user prompt to stdin and close it — keeps argv short for big prompts.
  proc.stdin.write(opts.prompt);
  proc.stdin.end();

  const exitCode: number | null = await new Promise((resolve) => {
    proc.on("exit", (code) => resolve(code));
    proc.on("error", (err: any) => {
      if (err?.code === "ENOENT") {
        // Surfaced via the resolved code path; let exit handler fire too.
        resolve(127);
      } else {
        resolve(1);
      }
    });
  });

  clearTimeout(timeout);
  if (opts.signal) opts.signal.removeEventListener("abort", onAbort);

  if (exitCode === 127) throw new ClaudeCliNotFoundError();
  if (exitCode !== 0) {
    throw new ClaudeCliError(`claude CLI exited with code ${exitCode}`, stderr.trim(), exitCode);
  }

  // The JSON output is one object: { type: "result", result: "...full text...", ... }
  let parsed: any;
  try {
    parsed = JSON.parse(stdout);
  } catch (e) {
    throw new ClaudeCliError(
      `Could not parse claude JSON output: ${(e as Error).message}\n--- stdout (first 500) ---\n${stdout.slice(0, 500)}`,
      stderr.trim(),
    );
  }

  if (parsed.is_error) {
    throw new ClaudeCliError(
      `claude returned an error: ${parsed.subtype ?? "unknown"} ${parsed.api_error_status ?? ""}`,
      stderr.trim(),
    );
  }

  // When --json-schema is used, Claude Code returns the conforming object in
  // `structured_output` and a human-readable summary in `result`. Callers
  // expect a JSON string they can JSON.parse, so re-serialize the structured
  // output. Otherwise return the plain text result.
  if (opts.jsonSchema && parsed.structured_output != null) {
    return JSON.stringify(parsed.structured_output);
  }
  const result = typeof parsed.result === "string" ? parsed.result : "";
  return result;
}

/**
 * Streaming text generation. Yields text deltas as they arrive.
 *
 * Internally uses `--output-format stream-json --include-partial-messages`
 * and parses Anthropic SSE-style content_block_delta events out of the JSONL.
 */
export async function* claudeStream(opts: ClaudeRunOptions): AsyncGenerator<string, void, unknown> {
  const args = buildArgs(opts, "stream-json");
  const proc = spawnClaude(args, opts.cwd);

  const onAbort = () => proc.kill("SIGTERM");
  if (opts.signal) {
    if (opts.signal.aborted) {
      proc.kill("SIGKILL");
      return;
    }
    opts.signal.addEventListener("abort", onAbort, { once: true });
  }

  const timeout = setTimeout(() => proc.kill("SIGTERM"), opts.timeoutMs ?? 300_000);

  proc.stdout.setEncoding("utf8");
  proc.stderr.setEncoding("utf8");

  let stderr = "";
  proc.stderr.on("data", (c: string) => (stderr += c));

  proc.stdin.write(opts.prompt);
  proc.stdin.end();

  // Bridge the node Readable into an async iterator over JSONL lines.
  let buffer = "";
  const queue: string[] = [];
  let resolveNext: (() => void) | null = null;
  let done = false;
  let exitCode: number | null = null;

  proc.stdout.on("data", (chunk: string) => {
    buffer += chunk;
    let nl = buffer.indexOf("\n");
    while (nl !== -1) {
      const line = buffer.slice(0, nl).trim();
      buffer = buffer.slice(nl + 1);
      if (line) queue.push(line);
      nl = buffer.indexOf("\n");
    }
    if (resolveNext) {
      const r = resolveNext;
      resolveNext = null;
      r();
    }
  });

  proc.on("exit", (code) => {
    if (buffer.trim()) queue.push(buffer.trim());
    buffer = "";
    exitCode = code;
    done = true;
    if (resolveNext) {
      const r = resolveNext;
      resolveNext = null;
      r();
    }
  });

  try {
    while (true) {
      while (queue.length > 0) {
        const line = queue.shift()!;
        let evt: any;
        try {
          evt = JSON.parse(line);
        } catch {
          continue;
        }
        // Partial message deltas — true streaming chunks.
        if (evt.type === "stream_event" && evt.event?.type === "content_block_delta") {
          const delta = evt.event.delta;
          if (delta?.type === "text_delta" && typeof delta.text === "string") {
            yield delta.text;
          }
          continue;
        }
        // Result event = end of stream. Stop yielding.
        if (evt.type === "result") {
          if (evt.is_error) {
            throw new ClaudeCliError(
              `claude error: ${evt.subtype ?? "unknown"} ${evt.api_error_status ?? ""}`,
              stderr.trim(),
            );
          }
          // Don't break here — let the proc exit close the loop, in case there
          // are remaining buffered events.
        }
      }
      if (done) break;
      await new Promise<void>((r) => (resolveNext = r));
    }

    if (exitCode === 127) throw new ClaudeCliNotFoundError();
    if (exitCode !== 0) {
      throw new ClaudeCliError(`claude CLI exited with code ${exitCode}`, stderr.trim(), exitCode);
    }
  } finally {
    clearTimeout(timeout);
    if (opts.signal) opts.signal.removeEventListener("abort", onAbort);
  }
}

/**
 * Multi-turn convenience. Sends a transcript of prior messages plus a new
 * user message, returns the assistant's full reply. Stateless from Claude's
 * perspective — your DB is the source of truth.
 */
export interface TranscriptMessage {
  role: "user" | "assistant";
  content: string;
}

export function formatTranscriptAsPrompt(transcript: TranscriptMessage[]): string {
  return transcript
    .map((m) => `<${m.role}>\n${m.content}\n</${m.role}>`)
    .join("\n\n");
}
