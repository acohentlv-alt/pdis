import { useState, useMemo, useEffect } from 'react';
import { useOpenSearchPresets, usePropertiesByPreset, useFavoriteIds, useWhitelistIds, useBlacklistIds } from '../api/queries';
import { useAddFavorite, useRemoveFavorite, useWhitelist, useRemoveWhitelist, useBlacklist, useRemoveBlacklist } from '../api/mutations';
import FilterBar from '../components/FilterBar';
import PropertyCard from '../components/PropertyCard';
import { formatDate } from '../lib/format';

function applyFilters(
  items: Record<string, unknown>[],
  neighborhoods: string[],
  selectedRooms: string[],
  sortBy: string,
  keyword: string
): Record<string, unknown>[] {
  let result = [...items];

  if (neighborhoods.length > 0) {
    result = result.filter(i => neighborhoods.includes(i.neighborhood as string));
  }
  if (selectedRooms.length > 0) {
    result = result.filter(i => {
      const r = i.rooms as number | null;
      if (r == null) return false;
      if (selectedRooms.includes('Studio') && r === 0) return true;
      if (selectedRooms.includes('6+') && r >= 6) return true;
      return selectedRooms.includes(String(r));
    });
  }
  if (keyword.trim()) {
    const kw = keyword.toLowerCase();
    result = result.filter(i => {
      const text = [
        i.description, i.address_street, i.neighborhood,
        i.contact_name, i.agent_office
      ].filter(Boolean).join(' ').toLowerCase();
      return text.includes(kw);
    });
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
  const [neighborhoods, setNeighborhoods] = useState<string[]>([]);
  const [selectedRooms, setSelectedRooms] = useState<string[]>([]);
  const [sortBy, setSortBy] = useState('distress_score');
  const [keyword, setKeyword] = useState('');
  const [debouncedKeyword, setDebouncedKeyword] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedKeyword(keyword), 300);
    return () => clearTimeout(timer);
  }, [keyword]);

  const { data: presetsData, isLoading: presetsLoading } = useOpenSearchPresets();
  const { data: propertiesData, isLoading: propsLoading } = usePropertiesByPreset(selectedPresetId);
  const { data: favIdsData } = useFavoriteIds();
  const { data: whitelistData } = useWhitelistIds();
  const { data: blacklistData } = useBlacklistIds();
  const favIds = useMemo(() => new Set(favIdsData?.ids ?? []), [favIdsData]);
  const whitelistIds = useMemo(() => new Set(whitelistData?.ids ?? []), [whitelistData]);
  const blacklistIds = useMemo(() => new Set(blacklistData?.ids ?? []), [blacklistData]);
  const addFav = useAddFavorite();
  const removeFav = useRemoveFavorite();
  const addWhitelist = useWhitelist();
  const removeWhitelist = useRemoveWhitelist();
  const addBlacklist = useBlacklist();
  const removeBlacklist = useRemoveBlacklist();
  const handleToggleFav = (yad2Id: string, isFav: boolean) => {
    if (isFav) removeFav.mutate(yad2Id);
    else addFav.mutate(yad2Id);
  };
  const handleToggleWhitelist = (yad2Id: string) => {
    if (whitelistIds.has(yad2Id)) removeWhitelist.mutate(yad2Id);
    else addWhitelist.mutate(yad2Id);
  };
  const handleToggleBlacklist = (yad2Id: string) => {
    if (blacklistIds.has(yad2Id)) removeBlacklist.mutate(yad2Id);
    else addBlacklist.mutate(yad2Id);
  };

  const rawItems = useMemo(() => {
    return (propertiesData?.properties ?? []) as Record<string, unknown>[];
  }, [propertiesData]);

  const filtered = useMemo(
    () => applyFilters(rawItems, neighborhoods, selectedRooms, sortBy, debouncedKeyword),
    [rawItems, neighborhoods, selectedRooms, sortBy, debouncedKeyword]
  );

  // Results view — a preset is selected
  if (selectedPresetId !== null) {
    const preset = presetsData?.presets.find(p => (p.id as number) === selectedPresetId);
    return (
      <div className="max-w-lg mx-auto px-4 py-4 space-y-4">
        <button
          onClick={() => {
            setSelectedPresetId(null);
            setNeighborhoods([]);
            setSelectedRooms([]);
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
          neighborhoods={neighborhoods}
          setNeighborhoods={setNeighborhoods}
          selectedRooms={selectedRooms}
          setSelectedRooms={setSelectedRooms}
          classification=""
          setClassification={() => {}}
          source=""
          setSource={() => {}}
          sortBy={sortBy}
          setSortBy={setSortBy}
          showClassificationFilter={false}
          keyword={keyword}
          setKeyword={setKeyword}
          minPriceSqm=""
          maxPriceSqm=""
          onMinPriceSqmChange={() => {}}
          onMaxPriceSqmChange={() => {}}
        />

        {propsLoading && (
          <div className="text-center text-gray-400 py-8">Loading…</div>
        )}

        {!propsLoading && filtered.length === 0 && (
          <div className="text-center text-gray-400 py-8">No properties found.</div>
        )}

        <div className="space-y-3 pb-8">
          {filtered.map(item => (
            <PropertyCard
              key={item.yad2_id as string}
              item={item}
              favoriteIds={favIds}
              onToggleFavorite={handleToggleFav}
              isWhitelisted={whitelistIds.has(item.yad2_id as string)}
              isBlacklisted={blacklistIds.has(item.yad2_id as string)}
              onToggleWhitelist={() => handleToggleWhitelist(item.yad2_id as string)}
              onToggleBlacklist={() => handleToggleBlacklist(item.yad2_id as string)}
            />
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
