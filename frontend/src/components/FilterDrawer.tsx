import { useEffect } from 'react';

const ROOM_OPTIONS = ['Studio', '1', '1.5', '2', '2.5', '3', '3.5', '4', '4.5', '5', '6+'];

const STRONG_SIGNALS = [
  { key: 'price_drop_gt_10pct', label: 'Price dropped > 10%' },
  { key: 'relisted_2plus', label: 'Relisted 2+ times' },
  { key: 'listed_90plus_days', label: 'Listed 90+ days' },
  { key: 'weak_language', label: 'Urgent language in description' },
  { key: 'condition_keywords', label: 'Needs renovation / old property' },
  { key: 'below_avg_price', label: 'Below average price' },
];

const WEAK_SIGNALS = [
  { key: 'price_drop_small', label: 'Price drop \u2264 10%' },
  { key: 'relisted_once', label: 'Relisted once' },
  { key: 'listed_30_60_days', label: 'Listed 30-60 days' },
  { key: 'desc_changes', label: 'Description changed' },
  { key: 'img_changes', label: 'Images changed' },
];

interface FilterDrawerProps {
  open: boolean;
  onClose: () => void;
  items: Record<string, unknown>[];
  minPrice: string;
  maxPrice: string;
  setMinPrice: (v: string) => void;
  setMaxPrice: (v: string) => void;
  selectedRooms: string[];
  setSelectedRooms: (v: string[]) => void;
  minSqm: string;
  maxSqm: string;
  setMinSqm: (v: string) => void;
  setMaxSqm: (v: string) => void;
  minPriceSqm: string;
  maxPriceSqm: string;
  setMinPriceSqm: (v: string) => void;
  setMaxPriceSqm: (v: string) => void;
  neighborhoods: string[];
  setNeighborhoods: (v: string[]) => void;
  source: string;
  setSource: (v: string) => void;
  signalFilters: string[];
  setSignalFilters: (v: string[]) => void;
}

function toggleValue(arr: string[], val: string): string[] {
  return arr.includes(val) ? arr.filter(v => v !== val) : [...arr, val];
}

export default function FilterDrawer({
  open,
  onClose,
  items,
  minPrice, maxPrice, setMinPrice, setMaxPrice,
  selectedRooms, setSelectedRooms,
  minSqm, maxSqm, setMinSqm, setMaxSqm,
  minPriceSqm, maxPriceSqm, setMinPriceSqm, setMaxPriceSqm,
  neighborhoods, setNeighborhoods,
  source, setSource,
  signalFilters, setSignalFilters,
}: FilterDrawerProps) {
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [open]);

  if (!open) return null;

  const uniqueNeighborhoods = Array.from(new Set(
    items.map(i => i.neighborhood as string).filter(Boolean)
  )).sort();

  function handleClearAll() {
    setMinPrice('');
    setMaxPrice('');
    setSelectedRooms([]);
    setMinSqm('');
    setMaxSqm('');
    setMinPriceSqm('');
    setMaxPriceSqm('');
    setNeighborhoods([]);
    setSource('');
    setSignalFilters([]);
  }

  const inputClass = 'flex-1 border border-gray-200 rounded-xl px-4 py-3 text-[15px] bg-gray-50 min-h-[48px] focus:bg-white focus:border-gray-900 focus:outline-none focus:ring-2 focus:ring-gray-900/10 transition-all placeholder:text-gray-400';
  const chipBase = 'px-4 py-2.5 text-sm rounded-full border transition-all whitespace-nowrap min-h-[44px] flex items-center font-medium';
  const chipActive = 'bg-gray-900 text-white border-gray-900 shadow-sm';
  const chipInactive = 'bg-white text-gray-700 border-gray-200 hover:border-gray-400';
  const sectionLabel = 'text-[11px] uppercase tracking-[0.08em] font-semibold text-gray-500 mb-3';

  return (
    <>
      {/* Backdrop with blur */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[55] animate-fade-in"
        onClick={onClose}
      />

      {/* Sheet */}
      <div
        className="fixed left-0 right-0 bg-white rounded-t-3xl z-[60] max-h-[88vh] overflow-y-auto shadow-2xl animate-slide-up"
        style={{ bottom: 'calc(4rem + env(safe-area-inset-bottom))' }}
      >
        {/* Drag handle */}
        <div className="sticky top-0 bg-white pt-3 pb-1 z-10">
          <div className="mx-auto w-10 h-1 bg-gray-300 rounded-full" />
        </div>

        {/* Header */}
        <div className="sticky top-4 bg-white px-5 pt-2 pb-3 flex items-center justify-between z-10 border-b border-gray-100">
          <span className="text-xl font-bold text-gray-900 tracking-tight">Filters</span>
          <div className="flex items-center gap-1">
            <button
              onClick={handleClearAll}
              className="text-sm text-blue-600 font-semibold min-h-[44px] px-3 rounded-lg hover:bg-blue-50 transition-colors"
            >
              Clear all
            </button>
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-full text-lg min-h-[44px] min-w-[44px] flex items-center justify-center transition-colors"
              aria-label="Close filters"
            >
              &#x2715;
            </button>
          </div>
        </div>

        <div className="px-5 py-5 space-y-6 pb-32">
          {/* Price (₪) */}
          <section>
            <div className={sectionLabel}>Price (₪)</div>
            <div className="flex gap-2.5">
              <input
                type="number"
                inputMode="numeric"
                value={minPrice}
                onChange={e => setMinPrice(e.target.value)}
                placeholder="Min"
                className={inputClass}
              />
              <input
                type="number"
                inputMode="numeric"
                value={maxPrice}
                onChange={e => setMaxPrice(e.target.value)}
                placeholder="Max"
                className={inputClass}
              />
            </div>
          </section>

          {/* Rooms */}
          <section>
            <div className={sectionLabel}>Rooms</div>
            <div className="flex flex-wrap gap-2">
              {ROOM_OPTIONS.map(r => (
                <button
                  key={r}
                  onClick={() => setSelectedRooms(toggleValue(selectedRooms, r))}
                  className={`${chipBase} ${selectedRooms.includes(r) ? chipActive : chipInactive}`}
                >
                  {r}
                </button>
              ))}
            </div>
          </section>

          {/* Sqm */}
          <section>
            <div className={sectionLabel}>Square meters</div>
            <div className="flex gap-2.5">
              <input
                type="number"
                inputMode="numeric"
                value={minSqm}
                onChange={e => setMinSqm(e.target.value)}
                placeholder="Min m²"
                className={inputClass}
              />
              <input
                type="number"
                inputMode="numeric"
                value={maxSqm}
                onChange={e => setMaxSqm(e.target.value)}
                placeholder="Max m²"
                className={inputClass}
              />
            </div>
          </section>

          {/* Price/Sqm */}
          <section>
            <div className={sectionLabel}>Price per m² (₪)</div>
            <div className="flex gap-2.5">
              <input
                type="number"
                inputMode="numeric"
                value={minPriceSqm}
                onChange={e => setMinPriceSqm(e.target.value)}
                placeholder="Min ₪/m²"
                className={inputClass}
              />
              <input
                type="number"
                inputMode="numeric"
                value={maxPriceSqm}
                onChange={e => setMaxPriceSqm(e.target.value)}
                placeholder="Max ₪/m²"
                className={inputClass}
              />
            </div>
          </section>

          {/* Neighborhood */}
          {uniqueNeighborhoods.length > 0 && (
            <section>
              <div className={sectionLabel}>Neighborhood</div>
              <div className="flex flex-wrap gap-2">
                {uniqueNeighborhoods.map(n => (
                  <button
                    key={n}
                    onClick={() => setNeighborhoods(toggleValue(neighborhoods, n))}
                    className={`${chipBase} ${neighborhoods.includes(n) ? chipActive : chipInactive}`}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </section>
          )}

          {/* Source */}
          <section>
            <div className={sectionLabel}>Source</div>
            <div className="grid grid-cols-4 gap-2">
              {(['', 'yad2', 'madlan', 'facebook'] as const).map(s => {
                const label = s === '' ? 'All' : s === 'yad2' ? 'Yad2' : s === 'madlan' ? 'Madlan' : 'Facebook';
                return (
                  <button
                    key={s}
                    onClick={() => setSource(s)}
                    className={`px-2 py-3 text-sm rounded-xl border transition-all min-h-[48px] font-medium ${
                      source === s ? chipActive : chipInactive
                    }`}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </section>

          {/* Signals */}
          <section>
            <div className={sectionLabel}>Signals</div>

            <div className="bg-gray-50 rounded-2xl p-4 mb-3">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-base">🚨</span>
                <span className="text-xs font-bold uppercase tracking-wider text-red-700">Strong signals</span>
              </div>
              <div className="space-y-1">
                {STRONG_SIGNALS.map(sig => (
                  <label
                    key={sig.key}
                    className="flex items-center gap-3 min-h-[44px] cursor-pointer rounded-lg px-2 -mx-2 hover:bg-white transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={signalFilters.includes(sig.key)}
                      onChange={() => setSignalFilters(toggleValue(signalFilters, sig.key))}
                      className="w-5 h-5 rounded-md border-gray-300 text-gray-900 shrink-0 focus:ring-gray-900/20"
                    />
                    <span className="text-sm text-gray-800 font-medium">{sig.label}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="bg-gray-50 rounded-2xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-base">⚠️</span>
                <span className="text-xs font-bold uppercase tracking-wider text-amber-700">Weak signals</span>
              </div>
              <div className="space-y-1">
                {WEAK_SIGNALS.map(sig => (
                  <label
                    key={sig.key}
                    className="flex items-center gap-3 min-h-[44px] cursor-pointer rounded-lg px-2 -mx-2 hover:bg-white transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={signalFilters.includes(sig.key)}
                      onChange={() => setSignalFilters(toggleValue(signalFilters, sig.key))}
                      className="w-5 h-5 rounded-md border-gray-300 text-gray-900 shrink-0 focus:ring-gray-900/20"
                    />
                    <span className="text-sm text-gray-800 font-medium">{sig.label}</span>
                  </label>
                ))}
              </div>
            </div>
          </section>
        </div>

        {/* Sticky Apply footer */}
        <div className="sticky bottom-0 left-0 right-0 bg-white border-t border-gray-100 px-5 py-4 shadow-[0_-4px_12px_rgba(0,0,0,0.04)]">
          <button
            onClick={onClose}
            className="w-full bg-gray-900 hover:bg-gray-800 active:bg-gray-700 text-white rounded-2xl py-4 text-base font-semibold transition-colors shadow-lg shadow-gray-900/20"
          >
            See results
          </button>
        </div>
      </div>
    </>
  );
}
