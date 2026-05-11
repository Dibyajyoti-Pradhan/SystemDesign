/**
 * BullMQ queue setup for async content generation.
 * Gracefully no-ops if UPSTASH_REDIS_URL / UPSTASH_REDIS_TOKEN are not set,
 * so the app can run (and be deployed) without a Redis credential.
 */

import type { Queue as BullQueue } from "bullmq";

export interface ContentJobData {
  type: "topic" | "cards";
  slug: string;
  userId: string;
}

const QUEUE_NAME = "careerlab-content";

function isRedisConfigured(): boolean {
  return !!(process.env.UPSTASH_REDIS_URL && process.env.UPSTASH_REDIS_TOKEN);
}

/**
 * Build the ioredis connection config for Upstash.
 * Upstash Redis uses TLS (`rediss://`) and token-based auth.
 */
function buildConnection() {
  const url = process.env.UPSTASH_REDIS_URL!;
  const token = process.env.UPSTASH_REDIS_TOKEN!;

  // Parse host / port from the URL (rediss://hostname:port)
  const parsed = new URL(url);
  return {
    host: parsed.hostname,
    port: parsed.port ? parseInt(parsed.port, 10) : 6380,
    password: token,
    tls: { rejectUnauthorized: false },
    maxRetriesPerRequest: null, // required by BullMQ
  };
}

// Lazily resolved so the module can be imported during Next.js build without
// needing Redis credentials at build time.
let _queue: BullQueue<ContentJobData> | null = null;

async function getQueue(): Promise<BullQueue<ContentJobData> | null> {
  if (!isRedisConfigured()) return null;
  if (_queue) return _queue;

  // Dynamic import so Next.js edge/build doesn't choke on node-only modules.
  const { Queue } = await import("bullmq");
  _queue = new Queue<ContentJobData>(QUEUE_NAME, {
    connection: buildConnection(),
    defaultJobOptions: {
      attempts: 3,
      backoff: { type: "exponential", delay: 5_000 },
      removeOnComplete: { count: 100 },
      removeOnFail: { count: 50 },
    },
  });
  return _queue;
}

/**
 * Exported singleton — null if Redis is not configured.
 * Prefer `enqueueContentJob` over accessing this directly; it handles the
 * async init for you. This export exists for callers that need queue introspection
 * (e.g. the admin panel reading waiting/active counts).
 *
 * Usage:
 *   const q = await getContentQueue();
 *   if (q) { const counts = await q.getJobCounts(); }
 */
export { getQueue as getContentQueue };

/**
 * Enqueue a content-generation job.
 * Returns the BullMQ job ID string, or null if the queue is unavailable.
 */
export async function enqueueContentJob(
  type: ContentJobData["type"],
  slug: string,
  userId: string,
): Promise<string | null> {
  const queue = await getQueue();
  if (!queue) return null;

  const job = await queue.add(
    `${type}:${slug}`,
    { type, slug, userId },
    { jobId: `${type}:${slug}:${Date.now()}` },
  );
  return job.id ?? null;
}
