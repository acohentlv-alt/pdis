// Sub-sections rendered inside PresetForm (pure JSX, no hooks)
import type { Dispatch, SetStateAction } from 'react';
import type {
  PresetFormData,
  PricingState,
  PricingRow,
  FaState,
  FaRow,
} from './presetFormUtils';
import {
  inputClass,
  chipBase,
  chipActive,
  chipInactive,
  sectionLabel,
  primaryCta as _primaryCta,
  PROPERTY_TYPE_OPTIONS,
  SIZE_BUCKETS,
  bucketKey,
  _DEFAULT_FA,
} from './presetFormUtils';

// ---------- Section A: Basics ----------

interface BasicsProps {
  form: PresetFormData;
  setField: (key: keyof PresetFormData, value: string | boolean) => void;
  category?: string;
}

const SOURCE_OPTIONS = [
  { value: 'yad2',             label: 'Yad2' },
  { value: 'madlan',           label: 'Madlan' },
  { value: 'facebook',         label: 'Facebook' },
  { value: 'yad2_madlan',      label: 'Yad2+Madlan' },
  { value: 'yad2_facebook',    label: 'Yad2+FB' },
  { value: 'madlan_facebook',  label: 'Madlan+FB' },
  { value: 'all',              label: 'All' },
];

export function SectionBasics({ form, setField, category }: BasicsProps) {
  return (
    <div className="space-y-4">
      {/* Name */}
      <div>
        <div className={sectionLabel}>Name *</div>
        <input
          className={`${inputClass} w-full`}
          value={form.name}
          onChange={e => setField('name', e.target.value)}
          placeholder="e.g. Tel Aviv 3-4 rooms"
        />
      </div>

      {/* Category chips — hidden if category prop passed */}
      {!category && (
        <div>
          <div className={sectionLabel}>Category</div>
          <div className="flex flex-wrap gap-2">
            {[{ value: 'rent', label: 'Rent' }, { value: 'forsale', label: 'For Sale' }].map(opt => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setField('category', opt.value)}
                className={`${chipBase} ${form.category === opt.value ? chipActive : chipInactive}`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Source chips */}
      <div>
        <div className={sectionLabel}>Source</div>
        <div className="flex flex-wrap gap-2">
          {SOURCE_OPTIONS.map(opt => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setField('source', opt.value)}
              className={`${chipBase} ${form.source === opt.value ? chipActive : chipInactive}`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* City code */}
      <div>
        <div className={sectionLabel}>City code *</div>
        <input
          className={`${inputClass} w-full`}
          value={form.city_code}
          onChange={e => setField('city_code', e.target.value)}
          placeholder="e.g. 5000"
        />
      </div>

      {/* Madlan city — only if source includes madlan */}
      {(['madlan', 'yad2_madlan', 'madlan_facebook', 'all', 'both'].includes(form.source)) && (
        <div>
          <div className={sectionLabel}>Madlan city (if different)</div>
          <input
            className={`${inputClass} w-full`}
            value={form.madlan_city}
            onChange={e => setField('madlan_city', e.target.value)}
            placeholder="Leave blank to use city code"
          />
        </div>
      )}
    </div>
  );
}

// ---------- Section B: Price & Rooms ----------

interface PriceRoomsProps {
  form: PresetFormData;
  setField: (key: keyof PresetFormData, value: string | boolean) => void;
}

export function SectionPriceRooms({ form, setField }: PriceRoomsProps) {
  return (
    <div className="space-y-4">
      <div>
        <div className={sectionLabel}>Price (₪)</div>
        <div className="flex gap-2.5">
          <input
            type="number"
            inputMode="numeric"
            className={`${inputClass} flex-1`}
            value={form.min_price}
            onChange={e => setField('min_price', e.target.value)}
            placeholder="Min"
          />
          <input
            type="number"
            inputMode="numeric"
            className={`${inputClass} flex-1`}
            value={form.max_price}
            onChange={e => setField('max_price', e.target.value)}
            placeholder="Max"
          />
        </div>
      </div>

      <div>
        <div className={sectionLabel}>Rooms</div>
        <div className="flex gap-2.5">
          <input
            type="number"
            step="0.5"
            inputMode="decimal"
            className={`${inputClass} flex-1`}
            value={form.min_rooms}
            onChange={e => setField('min_rooms', e.target.value)}
            placeholder="Min"
          />
          <input
            type="number"
            step="0.5"
            inputMode="decimal"
            className={`${inputClass} flex-1`}
            value={form.max_rooms}
            onChange={e => setField('max_rooms', e.target.value)}
            placeholder="Max"
          />
        </div>
      </div>
    </div>
  );
}

// ---------- Section C: More filters (collapsible) ----------

interface MoreFiltersProps {
  form: PresetFormData;
  setForm: Dispatch<SetStateAction<PresetFormData>>;
  setField: (key: keyof PresetFormData, value: string | boolean) => void;
  togglePropertyType: (val: string) => void;
  showAdvanced: boolean;
  setShowAdvanced: (v: boolean) => void;
  hoodData: { neighborhoods: { hood_id: number; neighborhood: string; listing_count: number }[] } | undefined;
  fbGroupsData: { groups: { group_id: string; name: string }[] } | undefined;
}

export function SectionMoreFilters({
  form,
  setForm,
  setField,
  togglePropertyType,
  showAdvanced,
  setShowAdvanced,
  hoodData,
  fbGroupsData,
}: MoreFiltersProps) {
  return (
    <div>
      {/* Toggle header */}
      <button
        type="button"
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="w-full flex items-center justify-between py-2"
      >
        <span className={sectionLabel.replace('mb-3', '')} style={{ marginBottom: 0 }}>
          More filters
        </span>
        <span className="text-gray-400 text-sm">{showAdvanced ? '▲' : '▼'}</span>
      </button>

      {showAdvanced && (
        <div className="space-y-5 mt-3">
          {/* Location */}
          <div>
            <div className={sectionLabel}>Location</div>
            <div className="bg-gray-50 rounded-2xl p-4 space-y-3">
              <input
                className={`${inputClass} w-full`}
                value={form.area_code}
                onChange={e => setField('area_code', e.target.value)}
                placeholder="Area code (e.g. 2)"
              />
              {/* Neighborhoods picker */}
              {(() => {
                const selectedHoods = new Set(
                  form.neighborhood?.split(',').filter(Boolean).map(Number) || []
                );
                return (
                  <div>
                    <div className="text-xs font-medium text-gray-500 mb-2">
                      Neighborhoods{selectedHoods.size > 0 ? ` · ${selectedHoods.size} selected` : ''}
                    </div>
                    <div className="max-h-48 overflow-y-auto space-y-1">
                      {(hoodData?.neighborhoods || []).map(h => {
                        const isChecked = selectedHoods.has(h.hood_id);
                        return (
                          <label key={h.hood_id} className="flex items-center gap-2 text-sm cursor-pointer hover:bg-white px-2 py-1 rounded-xl transition-colors">
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={() => {
                                const newSet = new Set(selectedHoods);
                                if (isChecked) {
                                  newSet.delete(h.hood_id);
                                } else {
                                  newSet.add(h.hood_id);
                                }
                                const newValue = Array.from(newSet).join(',');
                                setForm(prev => ({ ...prev, neighborhood: newValue }));
                              }}
                              className="w-5 h-5 rounded border-gray-200"
                            />
                            <span className="flex-1">{h.neighborhood}</span>
                            <span className="text-xs text-gray-400">{h.listing_count}</span>
                          </label>
                        );
                      })}
                      {(!hoodData?.neighborhoods || hoodData.neighborhoods.length === 0) && form.city_code && (
                        <div className="text-xs text-gray-400 py-2 text-center">No neighborhoods found for this city</div>
                      )}
                      {!form.city_code && (
                        <div className="text-xs text-gray-400 py-2 text-center">Enter a city code first</div>
                      )}
                    </div>
                  </div>
                );
              })()}
            </div>
          </div>

          {/* Property type chip group */}
          <div>
            <div className={sectionLabel}>Property Type</div>
            <div className="flex flex-wrap gap-2">
              {PROPERTY_TYPE_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => togglePropertyType(opt.value)}
                  className={`${chipBase} ${form.property_types.includes(opt.value) ? chipActive : chipInactive}`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Size & floor — 2×2 grid */}
          <div>
            <div className={sectionLabel}>Size & Floor</div>
            <div className="grid grid-cols-2 gap-2">
              <input type="number" className={`${inputClass} w-full`} value={form.min_sqm}
                onChange={e => setField('min_sqm', e.target.value)} placeholder="Min sqm" />
              <input type="number" className={`${inputClass} w-full`} value={form.max_sqm}
                onChange={e => setField('max_sqm', e.target.value)} placeholder="Max sqm" />
              <input type="number" className={`${inputClass} w-full`} value={form.min_floor}
                onChange={e => setField('min_floor', e.target.value)} placeholder="Min floor" />
              <input type="number" className={`${inputClass} w-full`} value={form.max_floor}
                onChange={e => setField('max_floor', e.target.value)} placeholder="Max floor" />
            </div>
          </div>

          {/* Move-in date */}
          <div>
            <div className={sectionLabel}>Move-in date</div>
            <input type="date" className={`${inputClass} w-full`} value={form.enter_date}
              onChange={e => setField('enter_date', e.target.value)} />
          </div>

          {/* Amenities chip group */}
          <div>
            <div className={sectionLabel}>Amenities</div>
            <div className="flex flex-wrap gap-2">
              {[
                { key: 'parking' as const,          label: 'Parking' },
                { key: 'elevator' as const,          label: 'Elevator' },
                { key: 'air_conditioning' as const,  label: 'A/C' },
                { key: 'balcony' as const,           label: 'Balcony' },
                { key: 'pets' as const,              label: 'Pets' },
                { key: 'furniture' as const,         label: 'Furnished' },
                { key: 'mamad' as const,             label: 'Mamad' },
                { key: 'accessible' as const,        label: 'Accessible' },
              ].map(({ key, label }) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setField(key, !form[key])}
                  className={`${chipBase} ${form[key] ? chipActive : chipInactive}`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Photos only toggle */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setField('img_only', !form.img_only)}
              className={`${chipBase} ${form.img_only ? chipActive : chipInactive}`}
            >
              Photos only
            </button>
          </div>

          {/* Property condition chips */}
          <div>
            <div className={sectionLabel}>Property Condition</div>
            <div className="flex flex-wrap gap-2">
              {[
                { value: '',  label: 'Any' },
                { value: '1', label: 'New (contractor)' },
                { value: '2', label: 'New' },
                { value: '3', label: 'Renovated' },
                { value: '4', label: 'Well maintained' },
                { value: '5', label: 'Needs work' },
                { value: '6', label: 'Preservation' },
              ].map(opt => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setField('property_condition', opt.value)}
                  className={`${chipBase} ${form.property_condition === opt.value ? chipActive : chipInactive}`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* FB groups — only if source includes facebook */}
          {['facebook', 'yad2_facebook', 'madlan_facebook', 'all'].includes(form.source) && (
            <div>
              <div className={sectionLabel}>Facebook groups</div>
              {(() => {
                const groups = fbGroupsData?.groups ?? [];
                if (groups.length === 0) {
                  return (
                    <div className="text-xs text-gray-500 bg-yellow-50 rounded-2xl p-4">
                      No Facebook groups discovered yet. Edit the catalog JSON on the VM and run <code className="bg-white px-1 rounded">scripts/seed_fb_groups.py</code> to populate this list.
                    </div>
                  );
                }
                const selected = new Set(form.fb_groups);
                return (
                  <>
                    {selected.size > 0 && (
                      <div className="text-xs text-gray-500 mb-2">{selected.size} selected</div>
                    )}
                    <div className="max-h-48 overflow-y-auto bg-gray-50 rounded-2xl p-3 space-y-1">
                      {groups.map(g => {
                        const isChecked = selected.has(g.group_id);
                        return (
                          <label key={g.group_id} className="flex items-center gap-2 text-sm cursor-pointer hover:bg-white px-2 py-1 rounded-xl transition-colors">
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={() => {
                                const next = new Set(selected);
                                if (isChecked) next.delete(g.group_id);
                                else next.add(g.group_id);
                                setForm(prev => ({ ...prev, fb_groups: Array.from(next) }));
                              }}
                              className="w-5 h-5 rounded border-gray-200"
                            />
                            <span className="flex-1">{g.name}</span>
                          </label>
                        );
                      })}
                    </div>
                  </>
                );
              })()}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------- Section D: Pricing Targets (forsale only) ----------

interface PricingTargetsProps {
  form: PresetFormData;
  hoodData: { neighborhoods: { hood_id: number; neighborhood: string; listing_count: number }[] } | undefined;
  pricingTargets: PricingState;
  setPricingTargets: Dispatch<SetStateAction<PricingState>>;
  pricingExpanded: boolean;
  setPricingExpanded: (v: boolean) => void;
  neighborhoodExpanded: Record<number, boolean>;
  setNeighborhoodExpanded: Dispatch<SetStateAction<Record<number, boolean>>>;
}

export function SectionPricingTargets({
  form,
  hoodData,
  pricingTargets,
  setPricingTargets,
  pricingExpanded,
  setPricingExpanded,
  neighborhoodExpanded,
  setNeighborhoodExpanded,
}: PricingTargetsProps) {
  return (
    <div className="border-t border-gray-100 pt-4">
      <button
        type="button"
        onClick={() => setPricingExpanded(!pricingExpanded)}
        className="w-full flex items-center justify-between py-2"
      >
        <span className="text-[11px] uppercase tracking-[0.08em] font-semibold text-gray-500">
          Pricing Targets (Amit Fit)
        </span>
        <span className="text-gray-400 text-sm">{pricingExpanded ? '▲' : '▼'}</span>
      </button>

      {pricingExpanded && (() => {
        const selectedHoodIds = form.neighborhood?.split(',').filter(Boolean).map(Number).filter((n: number) => !isNaN(n)) || [];
        if (selectedHoodIds.length === 0) {
          return <div className="text-xs text-gray-400 py-2 text-center">Select neighborhoods above first.</div>;
        }
        const hoodIdToName = new Map((hoodData?.neighborhoods || []).map((h) => [h.hood_id, h.neighborhood]));

        return (
          <div className="space-y-2 mt-2">
            <div className="text-[11px] text-gray-500 italic px-1">
              Targets are shared across all presets for this neighborhood.
            </div>
            {selectedHoodIds.map((hoodId: number) => {
              const name = hoodIdToName.get(hoodId);
              if (!name) return null;
              const isOpen = !!neighborhoodExpanded[hoodId];
              const hoodBuckets = pricingTargets[hoodId] || {};
              const filledCount = SIZE_BUCKETS.filter(([lo, hi]) => {
                const r = hoodBuckets[bucketKey(lo, hi)];
                return r && r.pref && r.max;
              }).length;

              return (
                <div key={hoodId} className="rounded-2xl bg-white border border-gray-200">
                  <button
                    type="button"
                    onClick={() => setNeighborhoodExpanded(prev => ({ ...prev, [hoodId]: !prev[hoodId] }))}
                    className="w-full flex items-center justify-between gap-2 px-4 py-3 text-sm text-gray-700 hover:bg-gray-50 rounded-2xl"
                  >
                    <span className="flex items-center gap-1 min-w-0">
                      <span className="flex-shrink-0">{isOpen ? '▲' : '▼'}</span>
                      <span dir="auto" className="truncate">{name}</span>
                    </span>
                    <span className="text-xs text-gray-400 flex-shrink-0 whitespace-nowrap">{filledCount}/{SIZE_BUCKETS.length} filled</span>
                  </button>
                  {isOpen && (
                    <div className="px-4 pb-4">
                      {/* Header row */}
                      <div className="grid grid-cols-3 gap-2 mb-2">
                        <div className="text-[10px] uppercase tracking-wide text-gray-400 font-semibold">Size</div>
                        <div className="text-[10px] uppercase tracking-wide text-gray-400 font-semibold">Preferred</div>
                        <div className="text-[10px] uppercase tracking-wide text-gray-400 font-semibold">Max</div>
                      </div>
                      {SIZE_BUCKETS.map(([lo, hi]) => {
                        const key = bucketKey(lo, hi);
                        const row: PricingRow = hoodBuckets[key] || { pref: '', max: '' };
                        const setRow = (patch: Partial<PricingRow>) => {
                          setPricingTargets(prev => ({
                            ...prev,
                            [hoodId]: { ...(prev[hoodId] || {}), [key]: { ...row, ...patch } },
                          }));
                        };
                        return (
                          <div key={key} className="grid grid-cols-3 gap-2 mb-2 items-center">
                            <div className="text-xs text-gray-600 font-medium">{lo}–{hi}</div>
                            <input type="number" step="100" min="0" className={`${inputClass} w-full`}
                              placeholder="₪/sqm" value={row.pref}
                              onChange={e => setRow({ pref: e.target.value })} />
                            <input type="number" step="100" min="0" className={`${inputClass} w-full`}
                              placeholder="₪/sqm" value={row.max}
                              onChange={e => setRow({ max: e.target.value })} />
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        );
      })()}
    </div>
  );
}

// ---------- Section E: Feature Adjustments (forsale only) ----------

interface FeatureAdjustmentsProps {
  form: PresetFormData;
  hoodData: { neighborhoods: { hood_id: number; neighborhood: string; listing_count: number }[] } | undefined;
  faTargets: FaState;
  setFaTargets: Dispatch<SetStateAction<FaState>>;
  faExpanded: boolean;
  setFaExpanded: (v: boolean) => void;
  faHoodExpanded: Record<number, boolean>;
  setFaHoodExpanded: Dispatch<SetStateAction<Record<number, boolean>>>;
}

export function SectionFeatureAdjustments({
  form,
  hoodData,
  faTargets,
  setFaTargets,
  faExpanded,
  setFaExpanded,
  faHoodExpanded,
  setFaHoodExpanded,
}: FeatureAdjustmentsProps) {
  return (
    <div className="border-t border-gray-100 pt-4">
      <button
        type="button"
        onClick={() => setFaExpanded(!faExpanded)}
        className="w-full flex items-center justify-between py-2"
      >
        <span className="text-[11px] uppercase tracking-[0.08em] font-semibold text-gray-500">
          Feature Adjustments (Amit Fit)
        </span>
        <span className="text-gray-400 text-sm">{faExpanded ? '▲' : '▼'}</span>
      </button>

      {faExpanded && (() => {
        const selectedHoodIds = form.neighborhood?.split(',').filter(Boolean).map(Number).filter((n: number) => !isNaN(n)) || [];
        if (selectedHoodIds.length === 0) {
          return <div className="text-xs text-gray-400 py-2 text-center">Select neighborhoods above first.</div>;
        }
        const hoodIdToName = new Map((hoodData?.neighborhoods || []).map((h) => [h.hood_id, h.neighborhood]));

        return (
          <div className="space-y-2 mt-2">
            <div className="text-[11px] text-gray-500 italic px-1">
              Adjustments are shared across all presets for this neighborhood. Defaults applied on first open.
            </div>
            {selectedHoodIds.map((hoodId: number) => {
              const name = hoodIdToName.get(hoodId);
              if (!name) return null;
              const isOpen = !!faHoodExpanded[hoodId];
              const row: FaRow = faTargets[hoodId] || _DEFAULT_FA;
              const setRow = (patch: Partial<FaRow>) => {
                setFaTargets(prev => ({
                  ...prev,
                  [hoodId]: { ...(prev[hoodId] || _DEFAULT_FA), ...patch },
                }));
              };

              return (
                <div key={hoodId} className="rounded-2xl bg-white border border-gray-200">
                  <button
                    type="button"
                    onClick={() => {
                      if (!faTargets[hoodId]) setFaTargets(prev => ({ ...prev, [hoodId]: _DEFAULT_FA }));
                      setFaHoodExpanded(prev => ({ ...prev, [hoodId]: !prev[hoodId] }));
                    }}
                    className="w-full flex items-center justify-between gap-2 px-4 py-3 text-sm text-gray-700 hover:bg-gray-50 rounded-2xl"
                  >
                    <span className="flex items-center gap-1 min-w-0">
                      <span className="flex-shrink-0">{isOpen ? '▲' : '▼'}</span>
                      <span dir="auto" className="truncate">{name}</span>
                    </span>
                    <span className="text-xs text-gray-400 flex-shrink-0">Feature tweaks</span>
                  </button>

                  {isOpen && (
                    <div className="px-4 pb-4 space-y-4">
                      {/* Year-built: 3-column grid */}
                      <div>
                        <div className="text-[11px] uppercase tracking-[0.08em] font-semibold text-gray-500 mb-2">Year Built (%)</div>
                        <div className="grid grid-cols-3 gap-2 mb-2">
                          <div className="text-[10px] uppercase tracking-wide text-gray-400 font-semibold">Bucket</div>
                          <div className="text-[10px] uppercase tracking-wide text-gray-400 font-semibold">Preferred %</div>
                          <div className="text-[10px] uppercase tracking-wide text-gray-400 font-semibold">Max %</div>
                        </div>
                        {[
                          { label: 'Old (<1960)',        pK: 'year_old_pref' as const,     mK: 'year_old_max' as const },
                          { label: 'Mid-Old (60–89)',    pK: 'year_mid_old_pref' as const, mK: 'year_mid_old_max' as const },
                          { label: 'Mid (90–09)',        pK: 'year_mid_pref' as const,     mK: 'year_mid_max' as const },
                          { label: 'New (≥2010)',        pK: 'year_new_pref' as const,     mK: 'year_new_max' as const },
                        ].map(b => (
                          <div key={b.label} className="grid grid-cols-3 gap-2 mb-2 items-center">
                            <div className="text-xs text-gray-600 font-medium">{b.label}</div>
                            <input type="number" step="0.5" className={`${inputClass} w-full`}
                              placeholder="%" value={row[b.pK]}
                              onChange={e => setRow({ [b.pK]: e.target.value } as Partial<FaRow>)} />
                            <input type="number" step="0.5" className={`${inputClass} w-full`}
                              placeholder="%" value={row[b.mK]}
                              onChange={e => setRow({ [b.mK]: e.target.value } as Partial<FaRow>)} />
                          </div>
                        ))}
                      </div>

                      {/* Walk-up: single row */}
                      <div>
                        <div className="text-[11px] uppercase tracking-[0.08em] font-semibold text-gray-500 mb-2">Walk-up Penalty</div>
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-gray-600 flex-1">% per floor, no elevator</span>
                          <input type="number" step="0.5" min="0" max="10" className={`${inputClass} w-28`}
                            placeholder="e.g. 3" value={row.walkup}
                            onChange={e => setRow({ walkup: e.target.value })} />
                        </div>
                        <div className="text-[11px] text-gray-400 mt-1">
                          Applied as negative. E.g. 3 = -3% per floor. Cap: 15%.
                        </div>
                      </div>

                      {/* Parking + Mamad: 3-column grid */}
                      <div>
                        <div className="text-[11px] uppercase tracking-[0.08em] font-semibold text-gray-500 mb-2">Bonuses</div>
                        <div className="grid grid-cols-3 gap-2 mb-2">
                          <div className="text-[10px] uppercase tracking-wide text-gray-400 font-semibold">Feature</div>
                          <div className="text-[10px] uppercase tracking-wide text-gray-400 font-semibold">Preferred</div>
                          <div className="text-[10px] uppercase tracking-wide text-gray-400 font-semibold">Max</div>
                        </div>
                        {/* Parking row */}
                        <div className="grid grid-cols-3 gap-2 mb-2 items-center">
                          <div className="text-xs text-gray-600 font-medium">Parking (₪)</div>
                          <input type="number" step="1000" min="0" className={`${inputClass} w-full`}
                            placeholder="₪" value={row.parking_pref}
                            onChange={e => setRow({ parking_pref: e.target.value })} />
                          <input type="number" step="1000" min="0" className={`${inputClass} w-full`}
                            placeholder="₪" value={row.parking_max}
                            onChange={e => setRow({ parking_max: e.target.value })} />
                        </div>
                        {/* Mamad row */}
                        <div className="grid grid-cols-3 gap-2 items-center">
                          <div className="text-xs text-gray-600 font-medium">Mamad (%)</div>
                          <input type="number" step="0.5" className={`${inputClass} w-full`}
                            placeholder="%" value={row.mamad_pref}
                            onChange={e => setRow({ mamad_pref: e.target.value })} />
                          <input type="number" step="0.5" className={`${inputClass} w-full`}
                            placeholder="%" value={row.mamad_max}
                            onChange={e => setRow({ mamad_max: e.target.value })} />
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        );
      })()}
    </div>
  );
}
