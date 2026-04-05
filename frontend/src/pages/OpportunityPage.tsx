import { useState, useMemo, useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import SummaryBar from '../components/SummaryBar';
import FilterBar from '../components/FilterBar';
import PropertyCard from '../components/PropertyCard';
import PresetManager from '../components/PresetManager';
import { usePresetProperties, useAllPresets, useFavoriteIds, useWhitelistIds, useBlacklistIds, useScanStatus } from '../api/queries';
import { useAddFavorite, useRemoveFavorite, useWhitelist, useRemoveWhitelist, useBlacklist, useRemoveBlacklist } from '../api/mutations';
import { matchesPresetCriteria, computeTargetPriceSqm } from '../lib/presetMatch';

function getPresetSummary(preset: Record<string, unknown>): string {
  const parts: string[] = [];

  const minRooms = preset.min_rooms as number | null;
  const maxRooms = preset.max_rooms as number | null;
  if (minRooms != null || maxRooms != null) {
    if (minRooms != null && maxRooms != null) {
      parts.push(`${minRooms}-${maxRooms} rooms`);
    } else if (minRooms != null) {
      parts.push(`${minRooms}+ rooms`);
    } else {
      parts.push(`Up to ${maxRooms} rooms`);
    }
  }

  const minPrice = preset.min_price as number | null;
  const maxPrice = preset.max_price as number | null;
  if (minPrice != null || maxPrice != null) {
    const fmt = (n: number) => n >= 1000000 ? `${(n / 1000000).toFixed(1)}M` : n >= 1000 ? `${Math.round(n / 1000)}K` : String(n);
    if (minPrice != null && maxPrice != null) {
      parts.push(`${fmt(minPrice)}-${fmt(maxPrice)}`);
    } else if (maxPrice != null) {
      parts.push(`Up to ${fmt(maxPrice)}`);
    } else {
      parts.push(`From ${fmt(minPrice!)}`);
    }
  }

  const extraParams = preset.extra_params as Record<string, unknown> | null;
  const minSqm = extraParams?.min_sqm as number | null | undefined;
  if (minSqm != null) {
    parts.push(`${minSqm}m²+`);
  }

  const propertyTypes = preset.property_types as string[] | null;
  if (propertyTypes && propertyTypes.length > 0) {
    const typeLabel = propertyTypes.map(t => t.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())).join(', ');
    parts.push(typeLabel);
  }

  const neighborhood = preset.neighborhood as string | null;
  if (neighborhood && neighborhood.trim()) {
    const hoodCount = neighborhood.split(',').filter(Boolean).length;
    if (hoodCount > 1) {
      parts.push(`${hoodCount} hoods`);
    }
  }

  return parts.join(' · ');
}

function applyFilters(
  items: Record<string, unknown>[],
  neighborhoods: string[],
  selectedRooms: string[],
  source: string,
  sortBy: string,
  keyword: string,
  minPriceSqm: string,
  maxPriceSqm: string
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
  if (source) {
    result = result.filter(i => i.source === source);
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

  // Price per sqm filter
  const minPSqm = minPriceSqm !== '' ? Number(minPriceSqm) : null;
  const maxPSqm = maxPriceSqm !== '' ? Number(maxPriceSqm) : null;
  if (minPSqm !== null || maxPSqm !== null) {
    result = result.filter(i => {
      const price = i.price as number | null;
      const sqm = (i.square_meter_build as number | null) || (i.square_meters as number | null);
      if (!price || !sqm || sqm === 0) return false;
      const priceSqm = price / sqm;
      if (minPSqm !== null && priceSqm < minPSqm) return false;
      if (maxPSqm !== null && priceSqm > maxPSqm) return false;
      return true;
    });
  }

  const signalCount = (item: Record<string, unknown>) => {
    const sd = (item.signal_details as Record<string, unknown>) ?? {};
    const strong = (sd.strong_signals as string[]) ?? [];
    const weak = (sd.weak_signals as string[]) ?? [];
    return strong.length + weak.length;
  };

  result.sort((a, b) => {
    if (sortBy === 'price') {
      return ((a.price as number) ?? 0) - ((b.price as number) ?? 0);
    }
    if (sortBy === 'price_sqm') {
      const aPsqm = ((a.price as number) ?? 0) / (((a.square_meter_build as number) || (a.square_meters as number)) || 1);
      const bPsqm = ((b.price as number) ?? 0) / (((b.square_meter_build as number) || (b.square_meters as number)) || 1);
      return aPsqm - bPsqm;
    }
    // default: longest on market first, then most signals
    const domDiff = ((b.days_on_market as number) ?? 0) - ((a.days_on_market as number) ?? 0);
    if (domDiff !== 0) return domDiff;
    return signalCount(b) - signalCount(a);
  });

  return result;
}

export default function OpportunityPage() {
  // ALL hooks must be before any early return — this is critical to avoid React error #310

  const queryClient = useQueryClient();

  // Preset selection state — persisted in localStorage
  const [selectedPresetId, setSelectedPresetId] = useState<number | null>(() => {
    const stored = localStorage.getItem('pdis_selected_preset');
    return stored ? Number(stored) : null;
  });

  // Filter state
  const [neighborhoods, setNeighborhoods] = useState<string[]>([]);
  const [selectedRooms, setSelectedRooms] = useState<string[]>([]);
  const [source, setSource] = useState('');
  const [sortBy, setSortBy] = useState('days_on_market');
  const [minPriceSqm, setMinPriceSqm] = useState('');
  const [maxPriceSqm, setMaxPriceSqm] = useState('');
  const [keyword, setKeyword] = useState('');
  const [debouncedKeyword, setDebouncedKeyword] = useState('');
  const [activeStatFilter, setActiveStatFilter] = useState<string | null>(null);
  const [showPresets, setShowPresets] = useState(false);

  // Keyword debounce
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedKeyword(keyword), 300);
    return () => clearTimeout(timer);
  }, [keyword]);

  // Data fetching
  const { data: presetsData } = useAllPresets();
  const allPresets = (presetsData?.presets ?? []) as Record<string, unknown>[];

  const { data: presetPropsData, isLoading } = usePresetProperties(selectedPresetId);
  const allItems = (presetPropsData?.properties ?? []) as Record<string, unknown>[];

  const { data: favData } = useFavoriteIds();
  const { data: whitelistData } = useWhitelistIds();
  const { data: blacklistData } = useBlacklistIds();
  const { data: scanStatus } = useScanStatus();

  const favIds = useMemo(() => new Set(favData?.ids ?? []), [favData]);
  const whitelistIds = useMemo(() => new Set(whitelistData?.ids ?? []), [whitelistData]);
  const blacklistIds = useMemo(() => new Set(blacklistData?.ids ?? []), [blacklistData]);

  const addFav = useAddFavorite();
  const removeFav = useRemoveFavorite();
  const addWhitelist = useWhitelist();
  const removeWhitelist = useRemoveWhitelist();
  const addBlacklist = useBlacklist();
  const removeBlacklist = useRemoveBlacklist();

  // Auto-select first preset if none selected
  useEffect(() => {
    if (selectedPresetId === null && allPresets.length > 0) {
      const firstId = allPresets[0].id as number;
      setSelectedPresetId(firstId);
      localStorage.setItem('pdis_selected_preset', String(firstId));
    }
  }, [allPresets, selectedPresetId]);

  // Bug 3: Detect scan completion and refresh data
  const prevRunning = useRef(false);
  useEffect(() => {
    const isRunning = scanStatus?.running ?? false;
    if (prevRunning.current && !isRunning) {
      // Scan just finished — refresh data
      queryClient.invalidateQueries({ queryKey: ['presetProperties'] });
      queryClient.invalidateQueries({ queryKey: ['presets'] });
    }
    prevRunning.current = isRunning;
  }, [scanStatus?.running, queryClient]);

  // SummaryBar stats derived from allItems (full set, not filtered)
  const summaryStats = useMemo(() => {
    const scanned = allItems.length;
    const priceDrops = allItems.filter(i => {
      const sd = (i.signal_details as Record<string, unknown>) ?? {};
      return (sd.price_drops as number ?? 0) > 0;
    }).length;
    const reappeared = allItems.filter(i => {
      const sd = (i.signal_details as Record<string, unknown>) ?? {};
      return (sd.relisting_count as number ?? 0) > 0 || !!(sd.has_relisting);
    }).length;
    return { scanned, priceDrops, reappeared };
  }, [allItems]);

  // Client-side stat filtering applied on top of allItems
  const rawItems = useMemo(() => {
    if (!activeStatFilter) return allItems;
    switch (activeStatFilter) {
      case 'scanned':
        return allItems;
      case 'price_drop':
        return allItems.filter(i => {
          const sd = (i.signal_details as Record<string, unknown>) ?? {};
          return (sd.price_drops as number ?? 0) > 0;
        });
      case 'relisting':
        return allItems.filter(i => {
          const sd = (i.signal_details as Record<string, unknown>) ?? {};
          return (sd.relisting_count as number ?? 0) > 0 || !!(sd.has_relisting);
        });
      default:
        return allItems;
    }
  }, [allItems, activeStatFilter]);

  const filtered = useMemo(
    () => applyFilters(rawItems, neighborhoods, selectedRooms, source, sortBy, debouncedKeyword, minPriceSqm, maxPriceSqm),
    [rawItems, neighborhoods, selectedRooms, source, sortBy, debouncedKeyword, minPriceSqm, maxPriceSqm]
  );

  // Phase 2: split filtered into matching vs other based on preset criteria
  const selectedPreset = allPresets.find(p => (p.id as number) === selectedPresetId) ?? null;

  const [matchingItems, otherItems] = useMemo(() => {
    if (!selectedPreset) return [filtered, [] as Record<string, unknown>[]];
    const matching: Record<string, unknown>[] = [];
    const other: Record<string, unknown>[] = [];
    for (const item of filtered) {
      if (matchesPresetCriteria(item, selectedPreset)) {
        matching.push(item);
      } else {
        other.push(item);
      }
    }
    return [matching, other];
  }, [filtered, selectedPreset]);

  const targetPriceSqm = useMemo(() =>
    selectedPreset ? computeTargetPriceSqm(selectedPreset) : null
  , [selectedPreset]);

  const greeting = (() => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  })();

  function selectPreset(id: number) {
    setSelectedPresetId(id);
    localStorage.setItem('pdis_selected_preset', String(id));
    setActiveStatFilter(null);
  }

  function handleStatClick(stat: string) {
    if (stat === 'scanned') {
      setActiveStatFilter(null);
      return;
    }
    setActiveStatFilter(prev => prev === stat ? null : stat);
  }

  function handleToggleFav(yad2Id: string, isFav: boolean) {
    if (isFav) removeFav.mutate(yad2Id);
    else addFav.mutate(yad2Id);
  }

  function handleToggleWhitelist(yad2Id: string) {
    if (whitelistIds.has(yad2Id)) removeWhitelist.mutate(yad2Id);
    else addWhitelist.mutate(yad2Id);
  }

  function handleToggleBlacklist(yad2Id: string) {
    if (blacklistIds.has(yad2Id)) removeBlacklist.mutate(yad2Id);
    else addBlacklist.mutate(yad2Id);
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      <div className="p-4 space-y-3">
        {/* Header: Greeting + Scan status + Refresh + Gear */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <p className="text-lg font-semibold text-gray-900">{greeting}, Shechter</p>
            {scanStatus?.running && (
              <span className="text-xs text-blue-500 animate-pulse">Scanning...</span>
            )}
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => queryClient.invalidateQueries({ queryKey: ['presetProperties', selectedPresetId] })}
              className="p-2 text-gray-500 hover:text-gray-800 text-lg"
            >↻</button>
            <button
              onClick={() => setShowPresets(true)}
              className="p-2 text-gray-500 hover:text-gray-800 text-xl"
            >⚙️</button>
          </div>
        </div>

        {/* Preset Pills */}
        <div className="flex gap-2 overflow-x-auto pb-1" style={{ scrollbarWidth: 'none' }}>
          {allPresets.map(p => {
            const id = p.id as number;
            const isSelected = id === selectedPresetId;
            const pillSummary = getPresetSummary(p);
            return (
              <button
                key={id}
                onClick={() => selectPreset(id)}
                className={`px-4 py-2 rounded-full whitespace-nowrap shrink-0 border transition-colors text-left ${
                  isSelected ? 'bg-gray-900 text-white border-gray-900' : 'bg-white text-gray-700 border-gray-300'
                }`}
              >
                <span className="block text-sm font-medium">{p.name as string}</span>
                {pillSummary && (
                  <span className="block text-[10px] opacity-70">{pillSummary}</span>
                )}
              </button>
            );
          })}
          <button
            onClick={() => setShowPresets(true)}
            className="px-4 py-2 text-sm rounded-full whitespace-nowrap shrink-0 border border-dashed border-gray-300 text-gray-500"
          >+</button>
        </div>

        {/* SummaryBar — stats from full allItems */}
        <SummaryBar
          scanned={summaryStats.scanned}
          priceDrops={summaryStats.priceDrops}
          reappeared={summaryStats.reappeared}
          onStatClick={handleStatClick}
          activeFilter={activeStatFilter}
        />

        {/* Active stat filter label */}
        {activeStatFilter && activeStatFilter !== 'scanned' && (
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <span>
              Showing:{' '}
              {activeStatFilter === 'price_drop'
                ? 'Price Drops'
                : activeStatFilter === 'relisting'
                ? 'Reappeared'
                : activeStatFilter}
            </span>
            <button onClick={() => setActiveStatFilter(null)} className="text-blue-600 text-xs">
              Clear
            </button>
          </div>
        )}

        {/* FilterBar */}
        <FilterBar
          items={rawItems}
          neighborhoods={neighborhoods}
          setNeighborhoods={setNeighborhoods}
          selectedRooms={selectedRooms}
          setSelectedRooms={setSelectedRooms}
          source={source}
          setSource={setSource}
          sortBy={sortBy}
          setSortBy={setSortBy}
          keyword={keyword}
          setKeyword={setKeyword}
          minPriceSqm={minPriceSqm}
          maxPriceSqm={maxPriceSqm}
          onMinPriceSqmChange={setMinPriceSqm}
          onMaxPriceSqmChange={setMaxPriceSqm}
        />

        {/* No presets empty state */}
        {allPresets.length === 0 && !isLoading && (
          <div className="text-center text-gray-400 py-8">
            No presets yet. Tap + to create your first search.
          </div>
        )}

        {/* Loading */}
        {isLoading && (
          <div className="text-center text-gray-400 py-8">Loading...</div>
        )}

        {/* Property list — split into matching and other */}
        <div className="space-y-3 pb-8">
          {matchingItems.map(item => (
            <PropertyCard
              key={item.yad2_id as string}
              item={item}
              favoriteIds={favIds}
              onToggleFavorite={handleToggleFav}
              isWhitelisted={whitelistIds.has(item.yad2_id as string)}
              isBlacklisted={blacklistIds.has(item.yad2_id as string)}
              onToggleWhitelist={() => handleToggleWhitelist(item.yad2_id as string)}
              onToggleBlacklist={() => handleToggleBlacklist(item.yad2_id as string)}
              targetPriceSqm={targetPriceSqm}
            />
          ))}
          {otherItems.length > 0 && (
            <>
              <div className="text-xs text-gray-400 uppercase tracking-wide pt-4 pb-1">Other results</div>
              {otherItems.map(item => (
                <PropertyCard
                  key={item.yad2_id as string}
                  item={item}
                  favoriteIds={favIds}
                  onToggleFavorite={handleToggleFav}
                  isWhitelisted={whitelistIds.has(item.yad2_id as string)}
                  isBlacklisted={blacklistIds.has(item.yad2_id as string)}
                  onToggleWhitelist={() => handleToggleWhitelist(item.yad2_id as string)}
                  onToggleBlacklist={() => handleToggleBlacklist(item.yad2_id as string)}
                  targetPriceSqm={targetPriceSqm}
                />
              ))}
            </>
          )}
          {!isLoading && matchingItems.length === 0 && otherItems.length === 0 && allPresets.length > 0 && (
            <div className="text-center text-gray-400 py-8">No properties match your filters.</div>
          )}
        </div>
      </div>

      {/* PresetManager */}
      <PresetManager open={showPresets} onClose={() => setShowPresets(false)} />
    </div>
  );
}
