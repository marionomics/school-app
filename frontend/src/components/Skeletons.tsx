export function FeedSkeleton() {
  return (
    <div className="flex flex-col divide-y">
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="flex gap-3 p-4">
          <div className="h-10 w-10 animate-pulse rounded-full bg-muted" />
          <div className="flex-1 space-y-2">
            <div className="h-3 w-24 animate-pulse rounded bg-muted" />
            <div className="h-3 w-full animate-pulse rounded bg-muted" />
            <div className="h-3 w-2/3 animate-pulse rounded bg-muted" />
          </div>
        </div>
      ))}
    </div>
  );
}
