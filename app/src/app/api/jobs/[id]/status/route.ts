import { NextRequest, NextResponse } from "next/server";
import { requireUser } from "@/lib/auth";
import { getContentQueue } from "@/lib/queue";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export type JobStatus = "waiting" | "active" | "completed" | "failed" | "delayed" | "unknown";

export interface JobStatusResponse {
  jobId: string;
  status: JobStatus | "unavailable";
  result?: unknown;
  error?: string;
}

export async function GET(
  _req: NextRequest,
  ctx: { params: Promise<{ id: string }> },
): Promise<NextResponse> {
  try {
    await requireUser();
  } catch {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const queue = await getContentQueue();
  if (!queue) {
    return NextResponse.json({ status: "unavailable" } satisfies Pick<JobStatusResponse, "status">);
  }

  const { id } = await ctx.params;
  const job = await queue.getJob(id);

  if (!job) {
    return NextResponse.json({ error: "Job not found" }, { status: 404 });
  }

  const state = await job.getState();

  const body: JobStatusResponse = {
    jobId: id,
    status: state as JobStatus,
  };

  if (state === "completed") {
    body.result = job.returnvalue;
  }
  if (state === "failed") {
    body.error = job.failedReason ?? "Unknown error";
  }

  return NextResponse.json(body);
}
