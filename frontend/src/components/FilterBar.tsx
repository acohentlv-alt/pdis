interface FilterBarProps {
  items: Record<string, unknown>[];
  neighborhoods: string[];
  setNeighborhoods: (v: string[]) => void;
  selectedRooms: string[];
  setSelectedRooms: (v: string[]) => void;
  classification: string;
  setClassification: (v: string) => void;
  source: string;
  setSource: (v: string) => void;
  sortBy: string;
  setSortBy: (v: string) => void;
  showClassificationFilter: boolean;
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
  classification,
  setClassification,
  source,
  setSource,
  sortBy,
  setSortBy,
  showClassificationFilter,
}: FilterBarProps) {
  const uniqueNeighborhoods = Array.from(new Set(
    items.map(i => i.neighborhood as string).filter(Boolean)
  )).sort();

  return (
    <div className="space-y-2 py-2">
      <div>
        <div className="text-xs text-gray-500 mb-1">Neighborhood</div>
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

        {showClassificationFilter && (
          <select
            value={classification}
            onChange={e => setClassification(e.target.value)}
            className="flex-1 min-w-[100px] border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
          >
            <option value="">All classes</option>
            <option value="hot">Hot</option>
            <option value="warm">Warm</option>
            <option value="cold">Cold</option>
          </select>
        )}

        <select
          value={sortBy}
          onChange={e => setSortBy(e.target.value)}
          className="flex-1 min-w-[130px] border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
        >
          <option value="distress_score">Most signals</option>
          <option value="price">Price</option>
          <option value="days_on_market">Days on market</option>
        </select>
      </div>
    </div>
  );
}
