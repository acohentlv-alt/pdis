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
          <label className="block text-xs font-medium text-gray-500 mb-1">City</label>
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
            <option value="rent">Rent</option>
            <option value="sale">Sale</option>
          </select>
        </div>

        {/* Price */}
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Min price (₪)</label>
          <input
            type="number"
            value={minPrice}
            onChange={e => setMinPrice(e.target.value)}
            placeholder="e.g. 5000"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Max price (₪)</label>
          <input
            type="number"
            value={maxPrice}
            onChange={e => setMaxPrice(e.target.value)}
            placeholder="e.g. 10000"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          />
        </div>

        {/* Rooms */}
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Min rooms</label>
          <input
            type="number"
            step="0.5"
            value={minRooms}
            onChange={e => setMinRooms(e.target.value)}
            placeholder="e.g. 2"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">Max rooms</label>
          <input
            type="number"
            step="0.5"
            value={maxRooms}
            onChange={e => setMaxRooms(e.target.value)}
            placeholder="e.g. 4"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          />
        </div>
      </div>

      <button
        type="submit"
        disabled={mutation.isPending}
        className="w-full min-h-[44px] bg-gray-900 text-white rounded-lg text-sm font-medium disabled:opacity-60 transition-opacity"
      >
        {mutation.isPending ? 'Scanning...' : 'Run Search'}
      </button>

      {mutation.isPending && (
        <p className="text-xs text-center text-gray-400">
          Scanning Yad2, this takes about a minute...
        </p>
      )}

      {mutation.isError && (
        <p className="text-xs text-center text-red-500">
          Scan failed. Please try again.
        </p>
      )}

      {result !== null && (
        <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-800 text-center">
          Scan complete —{' '}
          {result.new_listings !== undefined
            ? `${result.new_listings} new listings found`
            : 'results available'}
          {result.total_active !== undefined && ` (${result.total_active} total active)`}
        </div>
      )}
    </form>
  );
}
