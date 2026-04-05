import { useState, useMemo, useEffect } from 'react';
import FilterBar from '../components/FilterBar';
import PropertyCard from '../components/PropertyCard';
import { useFavorites, useFavoriteIds, useWhitelistIds, useBlacklistIds, useWhitelistProperties, useBlacklistProperties } from '../api/queries';
import { useAddFavorite, useRemoveFavorite, useWhitelist, useRemoveWhitelist, useBlacklist, useRemoveBlacklist } from '../api/mutations';

type Tab = 'favorites' | 'whitelist' | 'blacklist';

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

  result.sort((a, b) => {
    if (sortBy === 'price') {
      return ((a.price as number) ?? 0) - ((b.price as number) ?? 0);
    }
    if (sortBy === 'days_on_market') {
      return ((b.days_on_market as number) ?? 0) - ((a.days_on_market as number) ?? 0);
    }
    if (sortBy === 'price_sqm') {
      const aPsqm = ((a.price as number) ?? 0) / (((a.square_meter_build as number) || (a.square_meters as number)) || 1);
      const bPsqm = ((b.price as number) ?? 0) / (((b.square_meter_build as number) || (b.square_meters as number)) || 1);
      return aPsqm - bPsqm;
    }
    // default: distress_score
    return ((b.distress_score as number) ?? 0) - ((a.distress_score as number) ?? 0);
  });

  return result;
}

export default function FavoritesPage() {
  const [tab, setTab] = useState<Tab>('favorites');
  const [neighborhoods, setNeighborhoods] = useState<string[]>([]);
  const [selectedRooms, setSelectedRooms] = useState<string[]>([]);
  const [classification, setClassification] = useState('');
  const [source, setSource] = useState('');
  const [sortBy, setSortBy] = useState('distress_score');
  const [keyword, setKeyword] = useState('');
  const [debouncedKeyword, setDebouncedKeyword] = useState('');
  const [minPriceSqm, setMinPriceSqm] = useState('');
  const [maxPriceSqm, setMaxPriceSqm] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedKeyword(keyword), 300);
    return () => clearTimeout(timer);
  }, [keyword]);

  const { data: favData, isLoading: favLoading } = useFavorites();
  const { data: whitelistPropsData, isLoading: whitelistLoading } = useWhitelistProperties();
  const { data: blacklistPropsData, isLoading: blacklistLoading } = useBlacklistProperties();
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

  const favCount = favData?.favorites?.length ?? 0;
  const whitelistCount = whitelistPropsData?.total ?? 0;
  const blacklistCount = blacklistPropsData?.total ?? 0;

  const rawItems = useMemo(() => {
    if (tab === 'favorites') return (favData?.favorites ?? []) as Record<string, unknown>[];
    if (tab === 'whitelist') return (whitelistPropsData?.properties ?? []) as Record<string, unknown>[];
    return (blacklistPropsData?.properties ?? []) as Record<string, unknown>[];
  }, [tab, favData, whitelistPropsData, blacklistPropsData]);

  const isLoading = tab === 'favorites' ? favLoading : tab === 'whitelist' ? whitelistLoading : blacklistLoading;

  const filtered = useMemo(
    () => applyFilters(rawItems, neighborhoods, selectedRooms, source, sortBy, debouncedKeyword, minPriceSqm, maxPriceSqm),
    [rawItems, neighborhoods, selectedRooms, source, sortBy, debouncedKeyword, minPriceSqm, maxPriceSqm]
  );

  const emptyMessage =
    tab === 'favorites'
      ? 'No favorites yet. Tap the star on any property.'
      : tab === 'whitelist'
      ? 'No whitelisted properties. Use the green check on property cards.'
      : 'No blacklisted properties. Use the red X on property cards.';

  return (
    <div className="max-w-lg mx-auto px-4 py-4 space-y-4">
      <h1 className="text-xl font-bold text-gray-900">My Listings</h1>

      {/* Tab bar */}
      <div className="flex gap-2">
        <button
          onClick={() => setTab('favorites')}
          className={`flex-1 py-1.5 text-sm rounded-full font-medium ${
            tab === 'favorites' ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600'
          }`}
        >
          Favorites ({favCount})
        </button>
        <button
          onClick={() => setTab('whitelist')}
          className={`flex-1 py-1.5 text-sm rounded-full font-medium ${
            tab === 'whitelist' ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600'
          }`}
        >
          Whitelist ({whitelistCount})
        </button>
        <button
          onClick={() => setTab('blacklist')}
          className={`flex-1 py-1.5 text-sm rounded-full font-medium ${
            tab === 'blacklist' ? 'bg-gray-900 text-white' : 'bg-gray-100 text-gray-600'
          }`}
        >
          Blacklist ({blacklistCount})
        </button>
      </div>

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
        showClassificationFilter={false}
        keyword={keyword}
        setKeyword={setKeyword}
        minPriceSqm={minPriceSqm}
        maxPriceSqm={maxPriceSqm}
        onMinPriceSqmChange={setMinPriceSqm}
        onMaxPriceSqmChange={setMaxPriceSqm}
      />

      {isLoading && (
        <div className="text-center text-gray-400 py-8">Loading...</div>
      )}

      {!isLoading && rawItems.length === 0 && (
        <div className="text-center text-gray-400 py-8">{emptyMessage}</div>
      )}

      {!isLoading && rawItems.length > 0 && filtered.length === 0 && (
        <div className="text-center text-gray-400 py-8">No properties match the filters.</div>
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
