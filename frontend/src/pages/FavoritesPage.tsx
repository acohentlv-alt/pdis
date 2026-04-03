import { useState, useMemo, useEffect } from 'react';
import FilterBar from '../components/FilterBar';
import PropertyCard from '../components/PropertyCard';
import { useFavorites, useFavoriteIds, useWhitelistIds, useBlacklistIds } from '../api/queries';
import { useAddFavorite, useRemoveFavorite, useWhitelist, useRemoveWhitelist, useBlacklist, useRemoveBlacklist } from '../api/mutations';

function applyFilters(
  items: Record<string, unknown>[],
  neighborhoods: string[],
  selectedRooms: string[],
  source: string,
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

export default function FavoritesPage() {
  const [neighborhoods, setNeighborhoods] = useState<string[]>([]);
  const [selectedRooms, setSelectedRooms] = useState<string[]>([]);
  const [classification, setClassification] = useState('');
  const [source, setSource] = useState('');
  const [sortBy, setSortBy] = useState('distress_score');
  const [keyword, setKeyword] = useState('');
  const [debouncedKeyword, setDebouncedKeyword] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedKeyword(keyword), 300);
    return () => clearTimeout(timer);
  }, [keyword]);

  const { data: favData, isLoading } = useFavorites();
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

  const rawItems = useMemo(
    () => (favData?.favorites ?? []) as Record<string, unknown>[],
    [favData]
  );

  const filtered = useMemo(
    () => applyFilters(rawItems, neighborhoods, selectedRooms, source, sortBy, debouncedKeyword),
    [rawItems, neighborhoods, selectedRooms, source, sortBy, debouncedKeyword]
  );

  return (
    <div className="max-w-lg mx-auto px-4 py-4 space-y-4">
      <h1 className="text-xl font-bold text-gray-900">⭐ Favorites</h1>

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
      />

      {isLoading && (
        <div className="text-center text-gray-400 py-8">Loading…</div>
      )}

      {!isLoading && rawItems.length === 0 && (
        <div className="text-center text-gray-400 py-8">
          No favorites yet. Tap ☆ on any property to save it here.
        </div>
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
