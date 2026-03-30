import { useState, useMemo } from 'react';
import SummaryBar from '../components/SummaryBar';
import FilterBar from '../components/FilterBar';
import PropertyCard from '../components/PropertyCard';
import { useOpportunities, useClassifications } from '../api/queries';

type Tab = 'opportunities' | 'fullscan';

function applyFilters(
  items: Record<string, unknown>[],
  neighborhood: string,
  rooms: string,
  classification: string,
  sortBy: string,
  tab: Tab
): Record<string, unknown>[] {
  let result = [...items];

  if (neighborhood) {
    result = result.filter(i => i.neighborhood === neighborhood);
  }
  if (rooms) {
    result = result.filter(i => String(i.rooms ?? '') === rooms);
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
  const [neighborhood, setNeighborhood] = useState('');
  const [rooms, setRooms] = useState('');
  const [classification, setClassification] = useState('');
  const [sortBy, setSortBy] = useState('distress_score');

  const { data: oppsData, isLoading: oppsLoading } = useOpportunities();
  const { data: classData, isLoading: classLoading } = useClassifications();

  const rawItems = useMemo(() => {
    if (tab === 'opportunities') {
      return (oppsData?.opportunities ?? []) as Record<string, unknown>[];
    }
    return (classData?.classifications ?? []) as Record<string, unknown>[];
  }, [tab, oppsData, classData]);

  const filtered = useMemo(
    () => applyFilters(rawItems, neighborhood, rooms, classification, sortBy, tab),
    [rawItems, neighborhood, rooms, classification, sortBy, tab]
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
        neighborhood={neighborhood}
        setNeighborhood={setNeighborhood}
        rooms={rooms}
        setRooms={setRooms}
        classification={classification}
        setClassification={setClassification}
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
          <PropertyCard key={item.yad2_id as string} item={item} />
        ))}
      </div>
    </div>
  );
}
