import { useState, useMemo } from 'react';
import FilterBar from '../components/FilterBar';
import PropertyCard from '../components/PropertyCard';
import { useFavorites, useFavoriteIds } from '../api/queries';
import { useAddFavorite, useRemoveFavorite } from '../api/mutations';

function applyFilters(
  items: Record<string, unknown>[],
  neighborhood: string,
  rooms: string,
  source: string,
  sortBy: string
): Record<string, unknown>[] {
  let result = [...items];

  if (neighborhood) {
    result = result.filter(i => i.neighborhood === neighborhood);
  }
  if (rooms) {
    result = result.filter(i => String(i.rooms ?? '') === rooms);
  }
  if (source) {
    result = result.filter(i => i.source === source);
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
  const [neighborhood, setNeighborhood] = useState('');
  const [rooms, setRooms] = useState('');
  const [classification, setClassification] = useState('');
  const [source, setSource] = useState('');
  const [sortBy, setSortBy] = useState('distress_score');

  const { data: favData, isLoading } = useFavorites();
  const { data: favIdsData } = useFavoriteIds();
  const favIds = useMemo(() => new Set(favIdsData?.ids ?? []), [favIdsData]);
  const addFav = useAddFavorite();
  const removeFav = useRemoveFavorite();
  const handleToggleFav = (yad2Id: string, isFav: boolean) => {
    if (isFav) removeFav.mutate(yad2Id);
    else addFav.mutate(yad2Id);
  };

  const rawItems = useMemo(
    () => (favData?.favorites ?? []) as Record<string, unknown>[],
    [favData]
  );

  const filtered = useMemo(
    () => applyFilters(rawItems, neighborhood, rooms, source, sortBy),
    [rawItems, neighborhood, rooms, source, sortBy]
  );

  return (
    <div className="max-w-lg mx-auto px-4 py-4 space-y-4">
      <h1 className="text-xl font-bold text-gray-900">⭐ Favorites</h1>

      <FilterBar
        items={rawItems}
        neighborhood={neighborhood}
        setNeighborhood={setNeighborhood}
        rooms={rooms}
        setRooms={setRooms}
        classification={classification}
        setClassification={setClassification}
        source={source}
        setSource={setSource}
        sortBy={sortBy}
        setSortBy={setSortBy}
        showClassificationFilter={false}
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
          <PropertyCard key={item.yad2_id as string} item={item} favoriteIds={favIds} onToggleFavorite={handleToggleFav} />
        ))}
      </div>
    </div>
  );
}
