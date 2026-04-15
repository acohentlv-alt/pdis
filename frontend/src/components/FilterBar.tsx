interface FilterBarProps {
  sortBy: string;
  setSortBy: (v: string) => void;
  keyword: string;
  setKeyword: (v: string) => void;
  activeFilterCount?: number;
  onOpenDrawer?: () => void;
}

export default function FilterBar({
  sortBy,
  setSortBy,
  keyword,
  setKeyword,
  activeFilterCount = 0,
  onOpenDrawer,
}: FilterBarProps) {
  return (
    <div className="flex gap-2 py-2 items-center">
      {/* Keyword search */}
      <div className="relative flex-1">
        <svg
          className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"
          width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
        >
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.3-4.3" />
        </svg>
        <input
          type="text"
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          placeholder="Search keywords"
          className="w-full border border-gray-200 bg-gray-50 rounded-xl pl-9 pr-9 py-2 text-sm min-h-[44px] focus:bg-white focus:border-gray-900 focus:outline-none focus:ring-2 focus:ring-gray-900/10 transition-all placeholder:text-gray-400"
        />
        {keyword && (
          <button
            onClick={() => setKeyword('')}
            className="absolute right-1 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-700 hover:bg-gray-200 rounded-full text-xs min-h-[32px] min-w-[32px] flex items-center justify-center transition-colors"
            aria-label="Clear search"
          >
            &#x2715;
          </button>
        )}
      </div>

      {/* Sort */}
      <select
        value={sortBy}
        onChange={e => setSortBy(e.target.value)}
        className="border border-gray-200 bg-gray-50 rounded-xl px-3 py-2 text-sm font-medium text-gray-700 min-h-[44px] focus:bg-white focus:border-gray-900 focus:outline-none focus:ring-2 focus:ring-gray-900/10 transition-all"
      >
        <option value="days_on_market">Market time</option>
        <option value="price">Price</option>
        <option value="price_sqm">Price/sqm</option>
      </select>

      {/* Filters button */}
      {onOpenDrawer && (
        <button
          onClick={onOpenDrawer}
          className={`flex items-center gap-1.5 rounded-xl px-4 text-sm font-semibold min-h-[44px] whitespace-nowrap transition-all ${
            activeFilterCount > 0
              ? 'bg-gray-900 text-white shadow-md shadow-gray-900/20'
              : 'bg-gray-50 text-gray-700 border border-gray-200 hover:border-gray-400'
          }`}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z" />
          </svg>
          Filters
          {activeFilterCount > 0 && (
            <span className="bg-white text-gray-900 text-[11px] font-bold rounded-full min-w-[20px] h-5 px-1.5 flex items-center justify-center">
              {activeFilterCount}
            </span>
          )}
        </button>
      )}
    </div>
  );
}
