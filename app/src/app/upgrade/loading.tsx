export default function UpgradeLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-md space-y-4">
        <div className="h-9 w-40 rounded-md bg-muted animate-pulse mx-auto" />
        <div className="rounded-2xl border overflow-hidden">
          <div className="bg-primary/20 h-32" />
          <div className="p-8 space-y-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-4 rounded bg-muted animate-pulse" />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
