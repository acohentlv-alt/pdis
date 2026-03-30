import { useState, useMemo } from 'react';
import { useOpenSearchPresets, usePropertiesByPreset } from '../api/queries';
import FilterBar from '../components/FilterBar';
import PropertyCard from '../components/PropertyCard';
import { formatDate } from '../lib/format';

function applyFilters(
  items: Record<string, unknown>[],
  neighborhood: string,
  rooms: string,
  sortBy: string
): Record<string, unknown>[] {
  let result = [...items];

  if (neighborhood) {
    result = result.filter(i => i.neighborhood === neighborhood);
  }
  if (rooms) {
    result = result.filter(i => String(i.rooms ?? '') === rooms);
  }

  result.sort((a, b) => {
    if (sortBy === 'price') {
      return ((a.price as number) ?? 0) - ((b.price as number) ?? 0);
    }
    if (sortBy === 'days_on_market') {
      return ((b.days_on_market as number) ?? 0) - ((a.days_on_market as number) ?? 0);
    }
    // default: distress_score
    return ((b.distress_score as number) ?? 0) - ((a.distress_score as number) ?? 0);
  });

  return result;
}

export default function SearchResultsPage() {
  const [selectedPresetId, setSelectedPresetId] = useState<number | null>(null);
  const [neighborhood, setNeighborhood] = useState('');
  const [rooms, setRooms] = useState('');
  const [sortBy, setSortBy] = useState('distress_score');

  const { data: presetsData, isLoading: presetsLoading } = useOpenSearchPresets();
  const { data: propertiesData, isLoading: propsLoading } = usePropertiesByPreset(selectedPresetId);

  const rawItems = useMemo(() => {
    return (propertiesData?.properties ?? []) as Record<string, unknown>[];
  }, [propertiesData]);

  const filtered = useMemo(
    () => applyFilters(rawItems, neighborhood, rooms, sortBy),
    [rawItems, neighborhood, rooms, sortBy]
  );

  // Results view — a preset is selected
  if (selectedPresetId !== null) {
    const preset = presetsData?.presets.find(p => (p.id as number) === selectedPresetId);
    return (
      <div className="max-w-lg mx-auto px-4 py-4 space-y-4">
        <button
          onClick={() => {
            setSelectedPresetId(null);
            setNeighborhood('');
            setRooms('');
            setSortBy('distress_score');
          }}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800"
        >
          <span>←</span>
          <span>Back to queries</span>
        </button>

        {preset && (
          <h2 className="text-lg font-bold text-gray-900">
            {preset.name as string}
          </h2>
        )}

        <FilterBar
          items={rawItems}
          neighborhood={neighborhood}
          setNeighborhood={setNeighborhood}
          rooms={rooms}
          setRooms={setRooms}
          classification=""
          setClassification={() => {}}
          sortBy={sortBy}
          setSortBy={setSortBy}
          showClassificationFilter={false}
        />

        {propsLoading && (
          <div className="text-center text-gray-400 py-8">Loading…</div>
        )}

        {!propsLoading && filtered.length === 0 && (
          <div className="text-center text-gray-400 py-8">No properties found.</div>
        )}

        <div className="space-y-3 pb-8">
          {filtered.map(item => (
            <PropertyCard key={item.yad2_id as string} item={item} />
          ))}
        </div>
      </div>
    );
  }

  // Query list view
  const presets = presetsData?.presets ?? [];

  return (
    <div className="max-w-lg mx-auto px-4 py-4 space-y-4">
      <h1 className="text-xl font-bold text-gray-900">📋 Findings</h1>
      <p className="text-sm text-gray-500">
        Select a past search to view its results.
      </p>

      {presetsLoading && (
        <div className="text-center text-gray-400 py-8">Loading…</div>
      )}

      {!presetsLoading && presets.length === 0 && (
        <div className="text-center text-gray-400 py-8">
          No searches yet. Use Search to run a custom scan.
        </div>
      )}

      <div className="space-y-3 pb-8">
        {presets.map(preset => {
          const minPrice = preset.min_price as number | null;
          const maxPrice = preset.max_price as number | null;
          const minRooms = preset.min_rooms as number | null;
          const maxRooms = preset.max_rooms as number | null;
          const createdAt = preset.created_at as string | null;

          return (
            <button
              key={preset.id as number}
              onClick={() => setSelectedPresetId(preset.id as number)}
              className="w-full bg-white rounded-xl shadow p-4 text-left space-y-1 hover:shadow-md transition-shadow"
            >
              <div className="font-semibold text-gray-900 text-sm">{preset.name as string}</div>
              <div className="text-xs text-gray-500 flex flex-wrap gap-2">
                {(minPrice || maxPrice) && (
                  <span>
                    {minPrice ? `${minPrice.toLocaleString('he-IL')} ₪` : ''}
                    {minPrice && maxPrice ? ' – ' : ''}
                    {maxPrice ? `${maxPrice.toLocaleString('he-IL')} ₪` : ''}
                  </span>
                )}
                {(minRooms || maxRooms) && (
                  <span>
                    {minRooms ?? ''}
                    {minRooms && maxRooms ? '–' : ''}
                    {maxRooms ?? ''} rooms
                  </span>
                )}
                {createdAt && (
                  <span className="ml-auto text-gray-400">{formatDate(createdAt)}</span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
