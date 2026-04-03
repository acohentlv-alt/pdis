import { useState, useMemo, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import SummaryBar from '../components/SummaryBar';
import FilterBar from '../components/FilterBar';
import PropertyCard from '../components/PropertyCard';
import PresetManager from '../components/PresetManager';
import { useOpportunities, useClassifications, useFavoriteIds, usePropertiesByEvent, useWhitelistIds, useBlacklistIds, usePropertySearch } from '../api/queries';
import { useAddFavorite, useRemoveFavorite, useWhitelist, useRemoveWhitelist, useBlacklist, useRemoveBlacklist } from '../api/mutations';

type Tab = 'opportunities' | 'fullscan';

function applyFilters(
  items: Record<string, unknown>[],
  neighborhoods: string[],
  selectedRooms: string[],
  classification: string,
  source: string,
  sortBy: string,
  tab: Tab,
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
  if (source) {
    result = result.filter(i => i.source === source);
  }
  if (tab === 'fullscan' && classification) {
    result = result.filter(i => i.classification === classification);
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
    // default: by classification (hot > warm > cold), then updated_at
    const classOrder: Record<string, number> = { hot: 0, warm: 1, cold: 2 };
    const aClass = classOrder[(a.classification as string) ?? 'cold'] ?? 2;
    const bClass = classOrder[(b.classification as string) ?? 'cold'] ?? 2;
    if (aClass !== bClass) return aClass - bClass;
    return new Date((b.updated_at as string) ?? '').getTime() - new Date((a.updated_at as string) ?? '').getTime();
  });

  return result;
}

const STAT_LABELS: Record<string, string> = {
  price_drop: 'Price Drops',
  relisting: 'Reappeared',
};

interface OpportunityPageProps {
  category: 'rent' | 'forsale';
}

export default function OpportunityPage({ category }: OpportunityPageProps) {
  const title = category === 'rent' ? 'Rental Hunter' : 'Purchase Hunter';

  const [tab, setTab] = useState<Tab>('opportunities');
  const [neighborhoods, setNeighborhoods] = useState<string[]>([]);
  const [selectedRooms, setSelectedRooms] = useState<string[]>([]);
  const [classification, setClassification] = useState('');
  const [source, setSource] = useState('');
  const [sortBy, setSortBy] = useState('signals');
  const [searchParams, setSearchParams] = useSearchParams();
  const [keyword, setKeyword] = useState(searchParams.get('keyword') || '');
  const [debouncedKeyword, setDebouncedKeyword] = useState(searchParams.get('keyword') || '');
  const [showMenu, setShowMenu] = useState(false);
  const [showPresets, setShowPresets] = useState(false);
  const [activeStatFilter, setActiveStatFilter] = useState<string | null>(null);
  const [searchAllQuery, setSearchAllQuery] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedKeyword(keyword), 300);
    return () => clearTimeout(timer);
  }, [keyword]);

  useEffect(() => {
    const params = new URLSearchParams(searchParams);
    if (debouncedKeyword) {
      params.set('keyword', debouncedKeyword);
    } else {
      params.delete('keyword');
    }
    setSearchParams(params, { replace: true });
  }, [debouncedKeyword]);

  const { data: oppsData, isLoading: oppsLoading } = useOpportunities(category);
  const { data: classData, isLoading: classLoading } = useClassifications(category);
  const { data: favData } = useFavoriteIds();
  const { data: whitelistData } = useWhitelistIds();
  const { data: blacklistData } = useBlacklistIds();
  const { data: searchData, isLoading: searchLoading } = usePropertySearch(searchAllQuery, category);
  const { data: eventPropsData, isLoading: eventPropsLoading } = usePropertiesByEvent(
    activeStatFilter && activeStatFilter !== 'opportunities' ? activeStatFilter : null,
    category
  );
  const favIds = useMemo(() => new Set(favData?.ids ?? []), [favData]);
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

  const handleStatClick = (stat: string) => {
    setKeyword('');
    setDebouncedKeyword('');
    setSearchAllQuery('');
    setSearchParams({}, { replace: true });
    setNeighborhoods([]);
    setSelectedRooms([]);
    setSource('');
    setClassification('');
    if (stat === 'opportunities') {
      setTab('opportunities');
      setActiveStatFilter(null);
      return;
    }
    if (stat === 'fullscan') {
      setTab('fullscan');
      setActiveStatFilter(null);
      return;
    }
    setActiveStatFilter(prev => prev === stat ? null : stat);
  };

  const rawItems = useMemo(() => {
    if (activeStatFilter && activeStatFilter !== 'opportunities') {
      return (eventPropsData?.properties ?? []) as Record<string, unknown>[];
    }
    if (tab === 'opportunities') {
      return (oppsData?.opportunities ?? []) as Record<string, unknown>[];
    }
    return (classData?.classifications ?? []) as Record<string, unknown>[];
  }, [tab, oppsData, classData, activeStatFilter, eventPropsData]);

  const filtered = useMemo(
    () => applyFilters(rawItems, neighborhoods, selectedRooms, classification, source, sortBy, tab, debouncedKeyword),
    [rawItems, neighborhoods, selectedRooms, classification, source, sortBy, tab, debouncedKeyword]
  );

  const isLoading = activeStatFilter && activeStatFilter !== 'opportunities'
    ? eventPropsLoading
    : tab === 'opportunities' ? oppsLoading : classLoading;

  return (
    <div className="max-w-lg mx-auto px-4 py-4 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">{title}</h1>
        <div className="relative">
          <button
            onClick={() => setShowMenu(!showMenu)}
            className="p-2 text-gray-500 hover:text-gray-800 text-xl"
          >&#8942;</button>
          {showMenu && (
            <div className="absolute right-0 top-full mt-1 bg-white rounded-lg shadow-lg border py-1 z-50 min-w-[160px]">
              <button
                onClick={() => { setShowPresets(true); setShowMenu(false); }}
                className="w-full text-left px-4 py-2 text-sm hover:bg-gray-50"
              >Manage Presets</button>
            </div>
          )}
        </div>
      </div>

      <SummaryBar
        onStatClick={handleStatClick}
        activeFilter={activeStatFilter ?? (tab === 'fullscan' ? 'fullscan' : tab === 'opportunities' ? 'opportunities' : null)}
        category={category}
      />

      <FilterBar
        items={rawItems}
        neighborhoods={neighborhoods}
        setNeighborhoods={setNeighborhoods}
        selectedRooms={selectedRooms}
        setSelectedRooms={setSelectedRooms}
        classification={classification}
        setClassification={setClassification}
        source={source}
        setSource={setSource}
        sortBy={sortBy}
        setSortBy={setSortBy}
        showClassificationFilter={tab === 'fullscan' && !activeStatFilter}
        keyword={keyword}
        setKeyword={setKeyword}
      />

      {activeStatFilter && activeStatFilter !== 'opportunities' && activeStatFilter !== 'fullscan' && (
        <div className="flex items-center gap-2 px-1">
          <span className="text-sm text-gray-600 font-medium">
            Showing: {STAT_LABELS[activeStatFilter] ?? activeStatFilter}
          </span>
          <button
            onClick={() => { setActiveStatFilter(null); setTab('opportunities'); }}
            className="text-xs text-gray-400 hover:text-gray-700 underline"
          >
            Clear
          </button>
        </div>
      )}

      {isLoading && (
        <div className="text-center text-gray-400 py-8">Loading…</div>
      )}

      {/* Search all properties mode */}
      {searchAllQuery && (
        <div className="flex items-center gap-2 px-1">
          <span className="text-sm text-gray-600 font-medium">
            Searching all properties for "{searchAllQuery}"
            {searchData && ` — ${searchData.properties.length} result${searchData.properties.length !== 1 ? 's' : ''}`}
          </span>
          <button
            onClick={() => setSearchAllQuery('')}
            className="text-xs text-gray-400 hover:text-gray-700 underline"
          >
            Clear
          </button>
        </div>
      )}

      {!isLoading && !searchAllQuery && filtered.length === 0 && (
        <div className="text-center text-gray-400 py-8 space-y-2">
          <div>No properties found.</div>
          {debouncedKeyword.length >= 2 && (
            <button
              onClick={() => setSearchAllQuery(debouncedKeyword)}
              className="text-sm text-blue-600 hover:text-blue-800 underline"
            >
              Search all properties for "{debouncedKeyword}"
            </button>
          )}
        </div>
      )}

      {searchLoading && searchAllQuery && (
        <div className="text-center text-gray-400 py-8">Searching…</div>
      )}

      <div className="space-y-3 pb-8">
        {searchAllQuery
          ? (searchData?.properties ?? []).map(item => (
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
            ))
          : filtered.map(item => (
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
            ))
        }
      </div>

      <PresetManager open={showPresets} onClose={() => setShowPresets(false)} category={category} />
    </div>
  );
}
