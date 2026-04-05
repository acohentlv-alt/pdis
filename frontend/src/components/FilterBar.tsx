import { useState } from 'react';

interface FilterBarProps {
  items: Record<string, unknown>[];
  neighborhoods: string[];
  setNeighborhoods: (v: string[]) => void;
  selectedRooms: string[];
  setSelectedRooms: (v: string[]) => void;
  source: string;
  setSource: (v: string) => void;
  sortBy: string;
  setSortBy: (v: string) => void;
  keyword: string;
  setKeyword: (v: string) => void;
  minPriceSqm: string;
  maxPriceSqm: string;
  onMinPriceSqmChange: (v: string) => void;
  onMaxPriceSqmChange: (v: string) => void;
}

const ROOM_OPTIONS = ['Studio', '1', '1.5', '2', '2.5', '3', '3.5', '4', '4.5', '5', '6+'];

function toggleValue(arr: string[], val: string): string[] {
  return arr.includes(val) ? arr.filter(v => v !== val) : [...arr, val];
}

export default function FilterBar({
  items,
  neighborhoods,
  setNeighborhoods,
  selectedRooms,
  setSelectedRooms,
  source,
  setSource,
  sortBy,
  setSortBy,
  keyword,
  setKeyword,
  minPriceSqm,
  maxPriceSqm,
  onMinPriceSqmChange,
  onMaxPriceSqmChange,
}: FilterBarProps) {
  const [showNeighborhoods, setShowNeighborhoods] = useState(false);

  const uniqueNeighborhoods = Array.from(new Set(
    items.map(i => i.neighborhood as string).filter(Boolean)
  )).sort();

  return (
    <div className="space-y-2 py-2">
      <div className="relative">
        <input
          type="text"
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          placeholder="Search keywords..."
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white pr-8"
        />
        {keyword && (
          <button
            onClick={() => setKeyword('')}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-sm"
          >&#x2715;</button>
        )}
      </div>

      <div>
        <button
          onClick={() => setShowNeighborhoods(v => !v)}
          className="text-xs text-gray-500 mb-1 flex items-center gap-1 hover:text-gray-700"
        >
          <span>{showNeighborhoods ? '▲' : '▼'}</span>
          <span>Neighborhood{neighborhoods.length > 0 ? ` (${neighborhoods.length})` : ''}</span>
        </button>
        {showNeighborhoods && (
          <div className="flex gap-1.5 overflow-x-auto pb-1" style={{ scrollbarWidth: 'none' }}>
            <button
              onClick={() => setNeighborhoods([])}
              className={`px-3 py-1.5 text-sm rounded-full whitespace-nowrap shrink-0 border transition-colors ${
                neighborhoods.length === 0 ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-700 border-gray-300'
              }`}
            >All</button>
            {uniqueNeighborhoods.map(n => (
              <button
                key={n}
                onClick={() => setNeighborhoods(toggleValue(neighborhoods, n))}
                className={`px-3 py-1.5 text-sm rounded-full whitespace-nowrap shrink-0 border transition-colors ${
                  neighborhoods.includes(n) ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-700 border-gray-300'
                }`}
              >{n}</button>
            ))}
          </div>
        )}
      </div>

      <div>
        <div className="text-xs text-gray-500 mb-1">Rooms</div>
        <div className="flex gap-1.5 overflow-x-auto pb-1" style={{ scrollbarWidth: 'none' }}>
          <button
            onClick={() => setSelectedRooms([])}
            className={`px-3 py-1.5 text-sm rounded-full whitespace-nowrap shrink-0 border transition-colors ${
              selectedRooms.length === 0 ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-700 border-gray-300'
            }`}
          >All</button>
          {ROOM_OPTIONS.map(r => (
            <button
              key={r}
              onClick={() => setSelectedRooms(toggleValue(selectedRooms, r))}
              className={`px-3 py-1.5 text-sm rounded-full whitespace-nowrap shrink-0 border transition-colors ${
                selectedRooms.includes(r) ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-700 border-gray-300'
              }`}
            >{r}</button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <select
          value={source}
          onChange={e => setSource(e.target.value)}
          className="flex-1 min-w-[100px] border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
        >
          <option value="">All sources</option>
          <option value="yad2">Yad2</option>
          <option value="madlan">Madlan</option>
        </select>

        <select
          value={sortBy}
          onChange={e => setSortBy(e.target.value)}
          className="flex-1 min-w-[130px] border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
        >
          <option value="signals">Most signals</option>
          <option value="price">Price</option>
          <option value="days_on_market">Days on market</option>
          <option value="price_sqm">Price/sqm</option>
        </select>

        <input
          type="number"
          value={minPriceSqm}
          onChange={e => onMinPriceSqmChange(e.target.value)}
          placeholder="Min ₪/sqm"
          className="w-[100px] border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
        />
        <input
          type="number"
          value={maxPriceSqm}
          onChange={e => onMaxPriceSqmChange(e.target.value)}
          placeholder="Max ₪/sqm"
          className="w-[100px] border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
        />
      </div>
    </div>
  );
}
