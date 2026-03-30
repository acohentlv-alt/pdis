import { useState, useMemo } from 'react';
import SummaryBar from '../components/SummaryBar';
import FilterBar from '../components/FilterBar';
import PropertyCard from '../components/PropertyCard';
import { useOpportunities, useClassifications, useFavoriteIds } from '../api/queries';
import { useAddFavorite, useRemoveFavorite } from '../api/mutations';

type Tab = 'opportunities' | 'fullscan';

function applyFilters(
  items: Record<string, unknown>[],
  neighborhoods: string[],
  selectedRooms: string[],
  classification: string,
  source: string,
  sortBy: string,
  tab: Tab
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

export default function HomePage() {
  const [tab, setTab] = useState<Tab>('opportunities');
  const [neighborhoods, setNeighborhoods] = useState<string[]>([]);
  const [selectedRooms, setSelectedRooms] = useState<string[]>([]);
  const [classification, setClassification] = useState('');
  const [source, setSource] = useState('');
  const [sortBy, setSortBy] = useState('distress_score');

  const { data: oppsData, isLoading: oppsLoading } = useOpportunities();
  const { data: classData, isLoading: classLoading } = useClassifications();
  const { data: favData } = useFavoriteIds();
  const favIds = useMemo(() => new Set(favData?.ids ?? []), [favData]);
  const addFav = useAddFavorite();
  const removeFav = useRemoveFavorite();
  const handleToggleFav = (yad2Id: string, isFav: boolean) => {
    if (isFav) removeFav.mutate(yad2Id);
    else addFav.mutate(yad2Id);
  };

  const rawItems = useMemo(() => {
    if (tab === 'opportunities') {
      return (oppsData?.opportunities ?? []) as Record<string, unknown>[];
    }
    return (classData?.classifications ?? []) as Record<string, unknown>[];
  }, [tab, oppsData, classData]);

  const filtered = useMemo(
    () => applyFilters(rawItems, neighborhoods, selectedRooms, classification, source, sortBy, tab),
    [rawItems, neighborhoods, selectedRooms, classification, source, sortBy, tab]
  );

  const isLoading = tab === 'opportunities' ? oppsLoading : classLoading;

  return (
    <div className="max-w-lg mx-auto px-4 py-4 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">
          {new Date().getHours() < 12
            ? '☀️ Good morning, Shoubidu Properties'
            : new Date().getHours() < 18
            ? '👋 Good afternoon, Shoubidu Properties'
            : '🌙 Good evening, Shoubidu Properties'}
        </h1>
      </div>

      <SummaryBar />

      <div className="flex gap-2">
        <button
          onClick={() => setTab('opportunities')}
          className={`flex-1 min-h-[44px] rounded-lg text-sm font-medium transition-colors ${
            tab === 'opportunities'
              ? 'bg-gray-900 text-white'
              : 'bg-white border border-gray-300 text-gray-700'
          }`}
        >
          Opportunities
        </button>
        <button
          onClick={() => setTab('fullscan')}
          className={`flex-1 min-h-[44px] rounded-lg text-sm font-medium transition-colors ${
            tab === 'fullscan'
              ? 'bg-gray-900 text-white'
              : 'bg-white border border-gray-300 text-gray-700'
          }`}
        >
          Full Scan
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
        showClassificationFilter={tab === 'fullscan'}
      />

      {isLoading && (
        <div className="text-center text-gray-400 py-8">Loading…</div>
      )}

      {!isLoading && filtered.length === 0 && (
        <div className="text-center text-gray-400 py-8">No properties found.</div>
      )}

      <div className="space-y-3 pb-8">
        {filtered.map(item => (
          <PropertyCard key={item.yad2_id as string} item={item} favoriteIds={favIds} onToggleFavorite={handleToggleFav} />
        ))}
      </div>
    </div>
  );
}
