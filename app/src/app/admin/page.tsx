import { db } from "@/db/client";
import { topics } from "@/db/schema";
import { asc } from "drizzle-orm";

export const dynamic = "force-dynamic";

export default async function AdminDashboardPage() {
  const rows = await db
    .select({
      id: topics.id,
      slug: topics.slug,
      title: topics.title,
      generatedAt: topics.generatedAt,
      version: topics.version,
      generationStatus: topics.generationStatus,
    })
    .from(topics)
    .orderBy(asc(topics.categoryOrder), asc(topics.topicOrder), asc(topics.id));

  return (
    <div className="max-w-7xl mx-auto p-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Topics</h1>
        <p className="text-muted-foreground mt-1">{rows.length} topics in the database</p>
      </header>

      <div className="rounded-md border overflow-x-auto">
        <table className="w-full text-sm min-w-[600px]">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Topic</th>
              <th className="text-left px-4 py-3 font-medium">Version</th>
              <th className="text-left px-4 py-3 font-medium">Status</th>
              <th className="text-left px-4 py-3 font-medium">Generated At</th>
              <th className="text-left px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {rows.map((t) => (
              <tr key={t.id} className="hover:bg-muted/30">
                <td className="px-4 py-3">
                  <div className="font-medium">{t.title}</div>
                  <div className="text-xs text-muted-foreground">{t.slug}</div>
                </td>
                <td className="px-4 py-3 tabular-nums">{t.version}</td>
                <td className="px-4 py-3">
                  <span
                    className={
                      t.generationStatus === "done"
                        ? "text-green-600 dark:text-green-400"
                        : t.generationStatus === "error"
                          ? "text-red-600 dark:text-red-400"
                          : "text-yellow-600 dark:text-yellow-400"
                    }
                  >
                    {t.generationStatus}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {t.generatedAt ? t.generatedAt.toLocaleString() : "—"}
                </td>
                <td className="px-4 py-3">
                  <RegenerateButton slug={t.slug} />
                </td>
              </tr>
            ))}
            <tr className="bg-muted/20">
              <td colSpan={5} className="px-4 py-3 text-sm text-muted-foreground">
                Queue: N/A — Redis not configured
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RegenerateButton({ slug }: { slug: string }) {
  return (
    <form
      action={`/api/admin/topics/${slug}/regenerate`}
      method="POST"
    >
      <button
        type="submit"
        className="text-xs px-3 py-1.5 rounded border border-border hover:bg-accent transition-colors"
      >
        Regenerate
      </button>
    </form>
  );
}
