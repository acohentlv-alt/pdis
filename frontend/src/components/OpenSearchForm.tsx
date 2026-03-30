import { useState } from 'react';
import { useOpenSearch } from '../api/mutations';

interface OpenSearchResult {
  new_listings?: number;
  total_active?: number;
  [key: string]: unknown;
}

interface Props {
  onSuccess?: () => void;
}

export default function OpenSearchForm({ onSuccess }: Props) {
  const [cityCode] = useState('5000');
  const [minPrice, setMinPrice] = useState('');
  const [maxPrice, setMaxPrice] = useState('');
  const [minRooms, setMinRooms] = useState('');
  const [maxRooms, setMaxRooms] = useState('');
  const [category, setCategory] = useState('rent');
  const [result, setResult] = useState<OpenSearchResult | null>(null);

  const mutation = useOpenSearch();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setResult(null);

    const params: Parameters<typeof mutation.mutate>[0] = {
      city_code: cityCode,
      category,
    };
    if (minPrice) params.min_price = parseInt(minPrice, 10);
    if (maxPrice) params.max_price = parseInt(maxPrice, 10);
    if (minRooms) params.min_rooms = parseFloat(minRooms);
    if (maxRooms) params.max_rooms = parseFloat(maxRooms);

    mutation.mutate(params, {
      onSuccess: (data) => {
        setResult(data as OpenSearchResult);
        onSuccess?.();
      },
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white border border-gray-200 rounded-xl p-4 space-y-3"
    >
      <div className="grid grid-cols-2 gap-3">
        {/* City */}
        <div className="col-span-2">
          <label className="block text-xs font-medium text-gray-500 mb-1">Ville</label>
          <select
            value={cityCode}
            disabled
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-gray-50 text-gray-700"
          >
            <option value="5000">Tel Aviv</option>
          </select>
        </div>

        {/* Category */}
        <div className="col-span-2">
          <label className="block text-xs font-medium text-gray-500 mb-1">Type</label>
          <select
            value={category}
            onChange={e => setCategory(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          >
            <option value="rent">Location</option>
            <option value="sale">Vente</option>
          </select>
        </div>

        {/* Price */}
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Prix min (₪)</label>
          <input
            type="number"
            value={minPrice}
            onChange={e => setMinPrice(e.target.value)}
            placeholder="ex: 5000"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Prix max (₪)</label>
          <input
            type="number"
            value={maxPrice}
            onChange={e => setMaxPrice(e.target.value)}
            placeholder="ex: 10000"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          />
        </div>

        {/* Rooms */}
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Pièces min</label>
          <input
            type="number"
            step="0.5"
            value={minRooms}
            onChange={e => setMinRooms(e.target.value)}
            placeholder="ex: 2"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Pièces max</label>
          <input
            type="number"
            step="0.5"
            value={maxRooms}
            onChange={e => setMaxRooms(e.target.value)}
            placeholder="ex: 4"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          />
        </div>
      </div>

      <button
        type="submit"
        disabled={mutation.isPending}
        className="w-full min-h-[44px] bg-gray-900 text-white rounded-lg text-sm font-medium disabled:opacity-60 transition-opacity"
      >
        {mutation.isPending ? 'Scan en cours…' : 'Lancer la recherche'}
      </button>

      {mutation.isPending && (
        <p className="text-xs text-center text-gray-400">
          Scan Yad2 en cours, cela prend environ une minute…
        </p>
      )}

      {mutation.isError && (
        <p className="text-xs text-center text-red-500">
          Erreur lors du scan. Veuillez réessayer.
        </p>
      )}

      {result !== null && (
        <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-800 text-center">
          Scan terminé —{' '}
          {result.new_listings !== undefined
            ? `${result.new_listings} nouvelles annonces`
            : 'résultats disponibles'}
          {result.total_active !== undefined && ` (${result.total_active} actives au total)`}
        </div>
      )}
    </form>
  );
}
