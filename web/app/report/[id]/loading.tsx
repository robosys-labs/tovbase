export default function ReportLoading() {
  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10 animate-pulse">
      {/* Header Card Skeleton */}
      <div className="border border-gray-200 rounded-xl p-6 mb-8">
        <div className="flex items-start gap-5">
          <div className="w-[72px] h-[72px] rounded-full bg-gray-200 shrink-0" />
          <div className="flex-1 min-w-0 space-y-3">
            <div className="flex items-center gap-2">
              <div className="h-6 w-48 bg-gray-200 rounded" />
              <div className="h-5 w-20 bg-gray-200 rounded-full" />
            </div>
            <div className="h-4 w-40 bg-gray-200 rounded" />
            <div className="flex gap-1.5">
              <div className="h-5 w-16 bg-gray-200 rounded" />
              <div className="h-5 w-16 bg-gray-200 rounded" />
              <div className="h-5 w-16 bg-gray-200 rounded" />
            </div>
          </div>
        </div>
        <div className="flex gap-2 mt-5 pt-4 border-t border-gray-100">
          <div className="h-8 w-28 bg-gray-200 rounded-lg" />
          <div className="h-8 w-28 bg-gray-200 rounded-lg" />
        </div>
      </div>

      {/* Tabs Skeleton */}
      <div className="flex gap-1 mb-6">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-9 w-28 bg-gray-200 rounded-lg" />
        ))}
      </div>

      {/* Content Skeleton */}
      <div className="space-y-4">
        <div className="h-4 w-full bg-gray-200 rounded" />
        <div className="h-4 w-5/6 bg-gray-200 rounded" />
        <div className="h-4 w-4/6 bg-gray-200 rounded" />
        <div className="h-20 w-full bg-gray-100 rounded-lg mt-6" />
        <div className="h-4 w-3/4 bg-gray-200 rounded" />
        <div className="h-4 w-5/6 bg-gray-200 rounded" />
      </div>
    </div>
  );
}
