export default function ProfileLoading() {
  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10 animate-pulse">
      <div className="flex flex-col items-center text-center mb-10">
        <div className="w-24 h-24 rounded-full bg-gray-200" />
        <div className="mt-4 h-7 w-48 bg-gray-200 rounded" />
        <div className="mt-2 h-5 w-20 bg-gray-200 rounded-full" />
        <div className="flex gap-1.5 mt-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-5 w-16 bg-gray-200 rounded" />
          ))}
        </div>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-10">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="border border-gray-200 rounded-lg p-3">
            <div className="h-6 w-12 bg-gray-200 rounded mx-auto" />
            <div className="h-3 w-16 bg-gray-200 rounded mx-auto mt-1.5" />
          </div>
        ))}
      </div>
      <div className="border border-gray-200 rounded-xl p-6">
        <div className="h-4 w-24 bg-gray-200 rounded mb-4" />
        <div className="space-y-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i}>
              <div className="flex justify-between mb-1">
                <div className="h-3 w-32 bg-gray-200 rounded" />
                <div className="h-3 w-8 bg-gray-200 rounded" />
              </div>
              <div className="h-2 w-full bg-gray-100 rounded-full" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
