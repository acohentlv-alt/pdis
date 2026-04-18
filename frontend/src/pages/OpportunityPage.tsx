import { useState, useMemo, useEffect, useRef } from 'react';
import { logEvent } from '../lib/telemetry';
import { useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import SummaryBar from '../components/SummaryBar';
import FilterBar from '../components/FilterBar';
import FilterDrawer from '../components/FilterDrawer';
import PropertyCard from '../components/PropertyCard';
import PresetManager from '../components/PresetManager';
import PullToRefresh from '../components/PullToRefresh';
import { usePresetProperties, useAllPresets, useAmitFitProperties, useCustomSearch, useFavoriteIds, useWhitelistIds, useBlacklistIds, useScanStatus } from '../api/queries';
import { apiFetch } from '../api/client';
import type { CustomSearchCriteria } from '../api/queries';
import { useAddFavorite, useRemoveFavorite, useWhitelist, useRemoveWhitelist, useBlacklist, useRemoveBlacklist } from '../api/mutations';
import { matchesPresetCriteria } from '../lib/presetMatch';
import { signalCount } from '../lib/signalCount';
import { useToast } from '../lib/toast';

const AMIT_FIT_RENT_ID = -1;
const AMIT_FIT_BUY_ID = -3;
const CUSTOM_SEARCH_ID = -2;

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
  maxPriceSqm: string,
  minPrice: string,
  maxPrice: string,
  minSqm: string,
  maxSqm: string,
  signalFilters: string[]
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

  // Price range
  const minP = minPrice !== '' ? Number(minPrice) : null;
  const maxP = maxPrice !== '' ? Number(maxPrice) : null;
  if (minP !== null) result = result.filter(i => (i.price as number ?? 0) >= minP);
  if (maxP !== null) result = result.filter(i => (i.price as number ?? Infinity) <= maxP);

  // Sqm range
  const minS = minSqm !== '' ? Number(minSqm) : null;
  const maxS = maxSqm !== '' ? Number(maxSqm) : null;
  if (minS !== null) result = result.filter(i => ((i.square_meter_build as number) ?? (i.square_meters as number) ?? 0) >= minS);
  if (maxS !== null) result = result.filter(i => ((i.square_meter_build as number) ?? (i.square_meters as number) ?? Infinity) <= maxS);

  // Signal filter — OR semantics
  if (signalFilters.length > 0) {
    result = result.filter(i => {
      const sd = (i.signal_details as { strong_signals?: string[]; weak_signals?: string[] } | null) ?? {};
      const all = [...(sd.strong_signals ?? []), ...(sd.weak_signals ?? [])];
      return signalFilters.some(sig => all.includes(sig));
    });
  }

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
    return signalCount(b.signal_details) - signalCount(a.signal_details);
  });

  return result;
}

export default function OpportunityPage() {
  // ALL hooks must be before any early return — this is critical to avoid React error #310

  const queryClient = useQueryClient();
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

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
  const [minPrice, setMinPrice] = useState('');
  const [maxPrice, setMaxPrice] = useState('');
  const [minSqm, setMinSqm] = useState('');
  const [maxSqm, setMaxSqm] = useState('');
  const [signalFilters, setSignalFilters] = useState<string[]>([]);
  const [keyword, setKeyword] = useState('');
  const [debouncedKeyword, setDebouncedKeyword] = useState('');
  const [activeStatFilter, setActiveStatFilter] = useState<string | null>(null);
  const [showPresets, setShowPresets] = useState(false);
  const [showDrawer, setShowDrawer] = useState(false);

  // Keyword debounce
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedKeyword(keyword), 300);
    return () => clearTimeout(timer);
  }, [keyword]);

  // Data fetching
  const { data: presetsData } = useAllPresets();
  const allPresetsRaw = (presetsData?.presets ?? []) as Record<string, unknown>[];
  const allPresets = useMemo(
    () => allPresetsRaw.filter(p => (p.is_visible as boolean) ?? true),
    [allPresetsRaw]
  );

  // Parse ?custom= URL param into criteria object
  const customCriteria = useMemo<CustomSearchCriteria | null>(() => {
    const raw = searchParams.get('custom');
    if (!raw) return null;
    try {
      const parsed = new URLSearchParams(decodeURIComponent(raw));
      const criteria: CustomSearchCriteria = {};
      if (parsed.get('city_code')) criteria.city_code = parsed.get('city_code')!;
      if (parsed.get('category')) criteria.category = parsed.get('category')!;
      const minPrice = parsed.get('min_price');
      if (minPrice) criteria.min_price = parseInt(minPrice, 10);
      const maxPrice = parsed.get('max_price');
      if (maxPrice) criteria.max_price = parseInt(maxPrice, 10);
      const minRooms = parsed.get('min_rooms');
      if (minRooms) criteria.min_rooms = parseFloat(minRooms);
      const maxRooms = parsed.get('max_rooms');
      if (maxRooms) criteria.max_rooms = parseFloat(maxRooms);
      return Object.keys(criteria).length > 0 ? criteria : null;
    } catch {
      return null;
    }
  }, [searchParams]);

  const isAmitFitRent = selectedPresetId === AMIT_FIT_RENT_ID;
  const isAmitFitBuy = selectedPresetId === AMIT_FIT_BUY_ID;
  const isAmitFit = isAmitFitRent || isAmitFitBuy;
  const isCustom = selectedPresetId === CUSTOM_SEARCH_ID;

  const { data: presetPropsData, isLoading: presetLoading } =
    usePresetProperties(isAmitFit || isCustom ? null : selectedPresetId);
  const { data: amitFitRentData, isLoading: amitRentLoading } =
    useAmitFitProperties('rent', isAmitFitRent);
  const { data: amitFitBuyData, isLoading: amitBuyLoading } =
    useAmitFitProperties('forsale', isAmitFitBuy);
  const { data: customData, isLoading: customLoading } =
    useCustomSearch(isCustom ? customCriteria : null);

  const isLoading = isAmitFitRent ? amitRentLoading : isAmitFitBuy ? amitBuyLoading : isCustom ? customLoading : presetLoading;
  const allItems = (
    isAmitFitRent
      ? (amitFitRentData?.properties ?? [])
      : isAmitFitBuy
      ? (amitFitBuyData?.properties ?? [])
      : isCustom
      ? (customData?.properties ?? [])
      : (presetPropsData?.properties ?? [])
  ) as Record<string, unknown>[];

  const { data: favData } = useFavoriteIds();
  const { data: whitelistData } = useWhitelistIds();
  const { data: blacklistData } = useBlacklistIds();
  const { data: scanStatus } = useScanStatus();

  // FB ingest health check — polled on mount
  const [fbHealthAlert, setFbHealthAlert] = useState(false);
  useEffect(() => {
    apiFetch<{ alert?: boolean }>('/api/ingest/facebook/health')
      .then((data) => { if (data.alert) setFbHealthAlert(true); })
      .catch(() => {/* ignore — non-critical */});
  }, []);

  const favIds = useMemo(() => new Set(favData?.ids ?? []), [favData]);
  const whitelistIds = useMemo(() => new Set(whitelistData?.ids ?? []), [whitelistData]);
  const blacklistIds = useMemo(() => new Set(blacklistData?.ids ?? []), [blacklistData]);

  const addFav = useAddFavorite();
  const removeFav = useRemoveFavorite();
  const addWhitelist = useWhitelist();
  const removeWhitelist = useRemoveWhitelist();
  const addBlacklist = useBlacklist();
  const removeBlacklist = useRemoveBlacklist();

  // Auto-select first preset if none selected or selection no longer visible
  useEffect(() => {
    if (allPresets.length === 0) return;
    if (selectedPresetId === AMIT_FIT_RENT_ID) return;
    if (selectedPresetId === AMIT_FIT_BUY_ID) return;
    if (selectedPresetId === CUSTOM_SEARCH_ID) return;
    const stillVisible = allPresets.some(p => (p.id as number) === selectedPresetId);
    if (selectedPresetId === null || !stillVisible) {
      const firstId = allPresets[0].id as number;
      setSelectedPresetId(firstId);
      localStorage.setItem('pdis_selected_preset', String(firstId));
    }
  }, [allPresets, selectedPresetId]);

  // Auto-select CUSTOM_SEARCH_ID when ?custom= param is present
  useEffect(() => {
    if (customCriteria && selectedPresetId !== CUSTOM_SEARCH_ID) {
      setSelectedPresetId(CUSTOM_SEARCH_ID);
      setActiveStatFilter(null);
    }
  }, [customCriteria, selectedPresetId]);

  // Recovery: if CUSTOM_SEARCH_ID selected but no criteria, fall back to first real preset
  useEffect(() => {
    if (selectedPresetId !== CUSTOM_SEARCH_ID) return;
    if (customCriteria) return;
    if (allPresets.length > 0) {
      selectPreset(allPresets[0].id as number);
    } else {
      setSelectedPresetId(null);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPresetId, customCriteria, allPresets]);

  // Detect scan completion and refresh data
  const prevRunning = useRef(false);
  useEffect(() => {
    const isRunning = scanStatus?.running ?? false;
    if (prevRunning.current && !isRunning) {
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
    () => applyFilters(
      rawItems, neighborhoods, selectedRooms, source, sortBy, debouncedKeyword,
      minPriceSqm, maxPriceSqm, minPrice, maxPrice, minSqm, maxSqm, signalFilters
    ),
    [rawItems, neighborhoods, selectedRooms, source, sortBy, debouncedKeyword,
     minPriceSqm, maxPriceSqm, minPrice, maxPrice, minSqm, maxSqm, signalFilters]
  );

  // Phase 2: split filtered into matching vs other based on preset criteria
  const selectedPreset = isAmitFit || isCustom
    ? null
    : (allPresets.find(p => (p.id as number) === selectedPresetId) ?? null);

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

  // Active filter count (keyword + sort excluded)
  const activeFilterCount = useMemo(() => (
    (minPrice ? 1 : 0) +
    (maxPrice ? 1 : 0) +
    (minSqm ? 1 : 0) +
    (maxSqm ? 1 : 0) +
    (minPriceSqm ? 1 : 0) +
    (maxPriceSqm ? 1 : 0) +
    (neighborhoods.length > 0 ? 1 : 0) +
    (selectedRooms.length > 0 ? 1 : 0) +
    (source ? 1 : 0) +
    (signalFilters.length > 0 ? 1 : 0)
  ), [minPrice, maxPrice, minSqm, maxSqm, minPriceSqm, maxPriceSqm, neighborhoods, selectedRooms, source, signalFilters]);

  // Empty state telemetry — one event per session per empty-state render, not per rerender
  const emptyStateLoggedRef = useRef<string | null>(null);
  useEffect(() => {
    if (isLoading) return;
    const view = isAmitFitRent ? 'amit_fit_rent' : isAmitFitBuy ? 'amit_fit_buy' : isCustom ? 'custom' : `preset_${selectedPresetId}`;
    const isEmpty = matchingItems.length === 0 && otherItems.length === 0 && allPresets.length > 0;
    if (isEmpty) {
      const key = `${view}:${JSON.stringify({ neighborhoods, selectedRooms, source, activeStatFilter })}`;
      if (emptyStateLoggedRef.current !== key) {
        emptyStateLoggedRef.current = key;
        logEvent('empty_state', { view, filters: { neighborhoods, selectedRooms, source, activeStatFilter } }, {}, 'warn');
      }
    } else {
      emptyStateLoggedRef.current = null;
    }
  }, [isLoading, matchingItems.length, otherItems.length, allPresets.length, isAmitFitRent, isAmitFitBuy, isCustom, selectedPresetId, neighborhoods, selectedRooms, source, activeStatFilter]);

  const greeting = (() => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  })();

  function selectPreset(id: number) {
    setSelectedPresetId(id);
    if (id !== CUSTOM_SEARCH_ID) {
      localStorage.setItem('pdis_selected_preset', String(id));
    }
    setActiveStatFilter(null);
  }

  // Note: AMIT_FIT_RENT_ID = -1 matches the old single-sentinel value, so existing
  // localStorage entries stored as -1 automatically resolve to the Rent pill.

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
    if (whitelistIds.has(yad2Id)) {
      removeWhitelist.mutate(yad2Id, { onSuccess: () => toast('Removed from whitelist') });
    } else {
      addWhitelist.mutate(yad2Id, { onSuccess: () => toast('\u2713 Whitelisted') });
    }
  }

  function handleToggleBlacklist(yad2Id: string) {
    if (blacklistIds.has(yad2Id)) {
      removeBlacklist.mutate(yad2Id, { onSuccess: () => toast('Removed from blacklist') });
    } else {
      addBlacklist.mutate(yad2Id, { onSuccess: () => toast('\u2713 Blacklisted') });
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      <PullToRefresh onRefresh={async () => { await queryClient.invalidateQueries({ queryKey: ['presetProperties', selectedPresetId] }); }}>
      <div className="p-4 space-y-3">
        {/* FB ingest health alert */}
        {fbHealthAlert && (
          <div className="bg-yellow-50 border border-yellow-200 text-yellow-800 text-sm px-3 py-2 rounded-lg">
            Facebook data not updating — check scraper
          </div>
        )}

        {/* Header: Greeting + Scan status + Refresh + Manage searches */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <p className="text-xl font-bold text-gray-900 tracking-tight truncate">{greeting}, Shechter</p>
            {scanStatus?.running && (
              <span className="text-xs text-blue-600 font-medium animate-pulse shrink-0">Scanning…</span>
            )}
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => setShowPresets(true)}
              className="w-10 h-10 rounded-full text-gray-500 hover:text-gray-900 hover:bg-gray-100 active:bg-gray-200 transition-colors flex items-center justify-center"
              title="Manage searches"
              aria-label="Manage search presets"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="4" y1="6" x2="14" y2="6" />
                <line x1="18" y1="6" x2="20" y2="6" />
                <circle cx="16" cy="6" r="2" />
                <line x1="4" y1="12" x2="8" y2="12" />
                <line x1="12" y1="12" x2="20" y2="12" />
                <circle cx="10" cy="12" r="2" />
                <line x1="4" y1="18" x2="16" y2="18" />
                <line x1="20" y1="18" x2="20" y2="18" />
                <circle cx="18" cy="18" r="2" />
              </svg>
            </button>
          </div>
        </div>

        {/* Preset Pills */}
        <div className="flex gap-2 overflow-x-auto pb-1" style={{ scrollbarWidth: 'none' }}>
          {customCriteria && (
            <button
              key="custom-search"
              onClick={() => selectPreset(CUSTOM_SEARCH_ID)}
              className={`px-4 py-2 rounded-full whitespace-nowrap shrink-0 border transition-colors text-left flex items-center gap-2 ${
                isCustom
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-blue-50 text-blue-700 border-blue-200'
              }`}
            >
              <span className="text-sm font-medium">Custom search</span>
              <span
                className="text-xs leading-none opacity-80 hover:opacity-100"
                onClick={(e) => {
                  e.stopPropagation();
                  setSearchParams({});
                  if (allPresets.length > 0) {
                    selectPreset(allPresets[0].id as number);
                  } else {
                    setSelectedPresetId(null);
                  }
                }}
                role="button"
                aria-label="Dismiss custom search"
              >
                ×
              </span>
            </button>
          )}
          <button
            key="amit-fit-rent"
            onClick={() => {
              setSelectedPresetId(AMIT_FIT_RENT_ID);
              localStorage.setItem('pdis_selected_preset', String(AMIT_FIT_RENT_ID));
              setActiveStatFilter(null);
            }}
            className={`px-4 py-2 rounded-full whitespace-nowrap shrink-0 border transition-colors text-left ${
              isAmitFitRent
                ? 'bg-emerald-600 text-white border-emerald-600'
                : 'bg-emerald-50 text-emerald-700 border-emerald-200'
            }`}
          >
            <span className="block text-sm font-medium">Amit Fit Rent</span>
            <span className="block text-[10px] opacity-70">Across all hoods</span>
          </button>
          <button
            key="amit-fit-buy"
            onClick={() => {
              setSelectedPresetId(AMIT_FIT_BUY_ID);
              localStorage.setItem('pdis_selected_preset', String(AMIT_FIT_BUY_ID));
              setActiveStatFilter(null);
            }}
            className={`px-4 py-2 rounded-full whitespace-nowrap shrink-0 border transition-colors text-left ${
              isAmitFitBuy
                ? 'bg-emerald-600 text-white border-emerald-600'
                : 'bg-emerald-50 text-emerald-700 border-emerald-200'
            }`}
          >
            <span className="block text-sm font-medium">Amit Fit Buy</span>
            <span className="block text-[10px] opacity-70">Across all hoods</span>
          </button>
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

        {/* FilterBar — keyword + sort + Filters button */}
        <FilterBar
          sortBy={sortBy}
          setSortBy={setSortBy}
          keyword={keyword}
          setKeyword={setKeyword}
          activeFilterCount={activeFilterCount}
          onOpenDrawer={() => setShowDrawer(true)}
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
                    />
              ))}
            </>
          )}
          {!isLoading && matchingItems.length === 0 && otherItems.length === 0 && allPresets.length > 0 && (
            <div className="text-center py-8">
              <div className="text-gray-400 mb-3">No properties match your filters.</div>
              {(activeFilterCount > 0 || activeStatFilter) && (
                <button
                  onClick={() => {
                    setMinPrice(''); setMaxPrice('');
                    setMinSqm(''); setMaxSqm('');
                    setMinPriceSqm(''); setMaxPriceSqm('');
                    setNeighborhoods([]); setSelectedRooms([]);
                    setSource(''); setSignalFilters([]);
                    setActiveStatFilter(null);
                  }}
                  className="text-sm text-blue-600 font-medium underline"
                >
                  Clear all filters
                </button>
              )}
            </div>
          )}
        </div>
      </div>
      </PullToRefresh>

      {/* PresetManager */}
      <PresetManager open={showPresets} onClose={() => setShowPresets(false)} />

      {/* Filter Drawer */}
      <FilterDrawer
        open={showDrawer}
        onClose={() => setShowDrawer(false)}
        items={rawItems}
        minPrice={minPrice}
        maxPrice={maxPrice}
        setMinPrice={setMinPrice}
        setMaxPrice={setMaxPrice}
        selectedRooms={selectedRooms}
        setSelectedRooms={setSelectedRooms}
        minSqm={minSqm}
        maxSqm={maxSqm}
        setMinSqm={setMinSqm}
        setMaxSqm={setMaxSqm}
        minPriceSqm={minPriceSqm}
        maxPriceSqm={maxPriceSqm}
        setMinPriceSqm={setMinPriceSqm}
        setMaxPriceSqm={setMaxPriceSqm}
        neighborhoods={neighborhoods}
        setNeighborhoods={setNeighborhoods}
        source={source}
        setSource={setSource}
        signalFilters={signalFilters}
        setSignalFilters={setSignalFilters}
      />
    </div>
  );
}
