import { Skeleton } from "@/components/ui/skeleton";

/** Matches the review layout: header strip, four record sections, sticky summary. */
export function ReviewSkeleton() {
  return (
    <div className="flex flex-col gap-8" aria-busy="true" aria-label="Loading intake" role="status" data-testid="review-skeleton">
      <span className="sr-only">Loading intake</span>
      <div className="flex flex-col gap-3">
        <Skeleton className="h-4 w-40" />
        <div className="flex items-start justify-between gap-6">
          <Skeleton className="h-9 w-72 max-w-full" />
          <Skeleton className="h-4 w-40" />
        </div>
        <div className="flex gap-3">
          <Skeleton className="h-6 w-28 rounded-full" />
          <Skeleton className="h-6 w-40" />
        </div>
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-8">
        <div className="flex flex-col gap-6">
          {[6, 5, 6, 5].map((rows, i) => (
            <div key={i} className="rounded-lg border border-border bg-card px-6 py-5 shadow-1">
              <Skeleton className="mb-4 h-6 w-28" />
              <div className="flex flex-col divide-y divide-hairline">
                {Array.from({ length: rows }).map((_, j) => (
                  <div key={j} className="grid grid-cols-1 gap-2 py-3 sm:grid-cols-[13rem_1fr]">
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-4 w-48 max-w-full" />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-4 rounded-lg border border-border bg-card p-6 shadow-1">
            <Skeleton className="h-4 w-36" />
            <Skeleton className="h-10 w-40 rounded-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <div className="mt-2 flex flex-col gap-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Skeleton className="h-11" />
            <Skeleton className="h-11" />
          </div>
          <Skeleton className="h-11" />
        </div>
      </div>
    </div>
  );
}
