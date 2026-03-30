interface FilterBarProps {
  items: Record<string, unknown>[];
  neighborhood: string;
  setNeighborhood: (v: string) => void;
  rooms: string;
  setRooms: (v: string) => void;
  classification: string;
  setClassification: (v: string) => void;
  sortBy: string;
  setSortBy: (v: string) => void;
  showClassificationFilter: boolean;
}

export default function FilterBar({
  items,
  neighborhood,
  setNeighborhood,
  rooms,
  setRooms,
  classification,
  setClassification,
  sortBy,
  setSortBy,
  showClassificationFilter,
}: FilterBarProps) {
  const neighborhoods = ['', ...Array.from(new Set(
    items.map(i => i.neighborhood as string).filter(Boolean)
  )).sort()];

  const roomValues = ['', ...Array.from(new Set(
    items.map(i => String(i.rooms ?? '')).filter(Boolean)
  )).sort((a, b) => parseFloat(a) - parseFloat(b))];

  return (
    <div className="flex flex-wrap gap-2 py-2">
      <select
        value={neighborhood}
        onChange={e => setNeighborhood(e.target.value)}
        className="flex-1 min-w-[120px] border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
      >
        <option value="">All neighborhoods</option>
        {neighborhoods.filter(Boolean).map(n => (
          <option key={n} value={n}>{n}</option>
        ))}
      </select>

      <select
        value={rooms}
        onChange={e => setRooms(e.target.value)}
        className="flex-1 min-w-[100px] border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
      >
        <option value="">All rooms</option>
        {roomValues.filter(Boolean).map(r => (
          <option key={r} value={r}>{r} rooms</option>
        ))}
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
  );
}
