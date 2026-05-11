export default function AdminLoading() {
  return (
    <div className="max-w-7xl mx-auto p-8 space-y-6">
      <div className="h-9 w-40 rounded-md bg-muted animate-pulse" />
      <div className="rounded-md border overflow-hidden">
        <div className="bg-muted/50 h-10 w-full" />
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex gap-4 px-4 py-3 border-t">
            <div className="flex-1 h-4 rounded bg-muted animate-pulse" />
            <div className="w-12 h-4 rounded bg-muted animate-pulse" />
            <div className="w-16 h-4 rounded bg-muted animate-pulse" />
            <div className="w-24 h-4 rounded bg-muted animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  )
}
