import { useState } from 'react';
import { useAllPresets, useNeighborhoods } from '../api/queries';
import {
  useCreatePreset,
  useUpdatePreset,
  useDeletePreset,
  useTogglePreset,
  useClonePreset,
  useScanPreset,
} from '../api/mutations';

interface PresetManagerProps {
  open: boolean;
  onClose: () => void;
  category?: string;
}

interface PresetFormData {
  name: string;
  source: string;
  city_code: string;
  madlan_city: string;
  min_price: string;
  max_price: string;
  min_rooms: string;
  max_rooms: string;
  is_active: boolean;
  category: string;
  // Advanced filters
  area_code: string;
  neighborhood: string;
  property_types: string[];
  min_sqm: string;
  max_sqm: string;
  min_floor: string;
  max_floor: string;
  enter_date: string;
  img_only: boolean;
  parking: boolean;
  elevator: boolean;
  air_conditioning: boolean;
  balcony: boolean;
  pets: boolean;
  furniture: boolean;
  mamad: boolean;
  accessible: boolean;
  property_condition: string;
}

const PROPERTY_TYPE_OPTIONS = [
  { value: 'apartment', label: 'Apartment' },
  { value: 'garden_apartment', label: 'Garden Apt' },
  { value: 'penthouse', label: 'Penthouse' },
  { value: 'mini_penthouse', label: 'Rooftop' },
  { value: 'studio', label: 'Studio/Loft' },
  { value: 'duplex', label: 'Duplex' },
  { value: 'house', label: 'House' },
  { value: 'cottage', label: 'Cottage' },
  { value: 'land', label: 'Land' },
  { value: 'housing_unit', label: 'Unit' },
  { value: 'other', label: 'Other' },
];

const emptyForm = (): PresetFormData => ({
  name: '',
  source: 'yad2',
  city_code: '',
  madlan_city: '',
  min_price: '',
  max_price: '',
  min_rooms: '',
  max_rooms: '',
  is_active: true,
  category: 'rent',
  area_code: '',
  neighborhood: '',
  property_types: [],
  min_sqm: '',
  max_sqm: '',
  min_floor: '',
  max_floor: '',
  enter_date: '',
  img_only: false,
  parking: false,
  elevator: false,
  air_conditioning: false,
  balcony: false,
  pets: false,
  furniture: false,
  mamad: false,
  accessible: false,
  property_condition: '',
});

function validate(form: PresetFormData): string | null {
  if (!form.name.trim()) return 'Name is required.';
  if (!form.city_code.trim()) return 'City code is required.';
  const minP = form.min_price !== '' ? Number(form.min_price) : null;
  const maxP = form.max_price !== '' ? Number(form.max_price) : null;
  if (minP !== null && maxP !== null && minP > maxP) return 'Min price must be ≤ max price.';
  const minR = form.min_rooms !== '' ? Number(form.min_rooms) : null;
  const maxR = form.max_rooms !== '' ? Number(form.max_rooms) : null;
  if (minR !== null && maxR !== null && minR > maxR) return 'Min rooms must be ≤ max rooms.';
  return null;
}

function formToPayload(form: PresetFormData): Record<string, unknown> {
  return {
    name: form.name.trim(),
    source: form.source,
    city_code: form.city_code.trim(),
    madlan_city: form.madlan_city.trim() || form.city_code.trim(),
    min_price: form.min_price !== '' ? Number(form.min_price) : null,
    max_price: form.max_price !== '' ? Number(form.max_price) : null,
    min_rooms: form.min_rooms !== '' ? Number(form.min_rooms) : null,
    max_rooms: form.max_rooms !== '' ? Number(form.max_rooms) : null,
    is_active: form.is_active,
    category: form.category,
    // Advanced filters
    area_code: form.area_code.trim() || null,
    neighborhood: form.neighborhood.trim() || null,
    property_types: form.property_types.length > 0 ? form.property_types : null,
    min_sqm: form.min_sqm !== '' ? Number(form.min_sqm) : null,
    max_sqm: form.max_sqm !== '' ? Number(form.max_sqm) : null,
    min_floor: form.min_floor !== '' ? Number(form.min_floor) : null,
    max_floor: form.max_floor !== '' ? Number(form.max_floor) : null,
    enter_date: form.enter_date || null,
    img_only: form.img_only || null,
    parking: form.parking || null,
    elevator: form.elevator || null,
    air_conditioning: form.air_conditioning || null,
    balcony: form.balcony || null,
    pets: form.pets || null,
    furniture: form.furniture || null,
    mamad: form.mamad || null,
    accessible: form.accessible || null,
    property_condition: form.property_condition || null,
  };
}

function presetToForm(preset: Record<string, unknown>): PresetFormData {
  const extra = (preset.extra_params ?? {}) as Record<string, unknown>;
  let source = 'yad2';
  if (extra.source === 'madlan') source = 'madlan';
  else if (extra.source === 'both') source = 'both';

  return {
    name: (preset.name as string) ?? '',
    source,
    city_code: (preset.city_code as string) ?? '',
    madlan_city: (extra.madlan_city as string) ?? '',
    min_price: preset.min_price != null ? String(preset.min_price) : '',
    max_price: preset.max_price != null ? String(preset.max_price) : '',
    min_rooms: preset.min_rooms != null ? String(preset.min_rooms) : '',
    max_rooms: preset.max_rooms != null ? String(preset.max_rooms) : '',
    is_active: (preset.is_active as boolean) ?? true,
    category: (preset.category as string) ?? 'rent',
    // Advanced filters — from DB columns
    area_code: (preset.area_code as string) ?? '',
    neighborhood: (preset.neighborhood as string) ?? '',
    property_types: (preset.property_types as string[]) ?? [],
    // Advanced filters — from extra_params
    min_sqm: extra.min_sqm != null ? String(extra.min_sqm) : '',
    max_sqm: extra.max_sqm != null ? String(extra.max_sqm) : '',
    min_floor: extra.min_floor != null ? String(extra.min_floor) : '',
    max_floor: extra.max_floor != null ? String(extra.max_floor) : '',
    enter_date: (extra.enter_date as string) ?? '',
    img_only: Boolean(extra.img_only),
    parking: Boolean(extra.parking),
    elevator: Boolean(extra.elevator),
    air_conditioning: Boolean(extra.air_conditioning),
    balcony: Boolean(extra.balcony),
    pets: Boolean(extra.pets),
    furniture: Boolean(extra.furniture),
    mamad: Boolean(extra.mamad),
    accessible: Boolean(extra.accessible),
    property_condition: (extra.property_condition as string) ?? '',
  };
}

function formatPriceRange(min: unknown, max: unknown): string {
  if (!min && !max) return '';
  const parts: string[] = [];
  if (min != null) parts.push(`${Number(min).toLocaleString('he-IL')} ₪`);
  if (max != null) parts.push(`${Number(max).toLocaleString('he-IL')} ₪`);
  return parts.join(' – ');
}

function formatRoomsRange(min: unknown, max: unknown): string {
  if (min == null && max == null) return '';
  if (min != null && max != null) return `${min}–${max} rooms`;
  if (min != null) return `${min}+ rooms`;
  return `up to ${max} rooms`;
}

function sourceLabel(preset: Record<string, unknown>): string {
  const extra = (preset.extra_params ?? {}) as Record<string, unknown>;
  if (extra.source === 'madlan') return 'Madlan';
  if (extra.source === 'both') return 'Yad2 + Madlan';
  return 'Yad2';
}

export default function PresetManager({ open, onClose, category }: PresetManagerProps) {
  // All hooks at top — before any conditional return
  const { data, isLoading } = useAllPresets();
  const createPreset = useCreatePreset();
  const updatePreset = useUpdatePreset();
  const deletePreset = useDeletePreset();
  const togglePreset = useTogglePreset();
  const clonePreset = useClonePreset();
  const scanPreset = useScanPreset();

  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<PresetFormData>(emptyForm());
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Must be before early return — hooks cannot be conditional
  const { data: hoodData } = useNeighborhoods(form.city_code || null);

  if (!open) return null;

  const presets = (data?.presets ?? []) as Record<string, unknown>[];

  function startCreate() {
    setForm({ ...emptyForm(), category: 'rent' });
    setFormError(null);
    setEditingId(null);
    setShowCreate(true);
    setShowAdvanced(false);
  }

  function startEdit(preset: Record<string, unknown>) {
    setForm(presetToForm(preset));
    setFormError(null);
    setEditingId(preset.id as number);
    setShowCreate(false);
    setShowAdvanced(false);
  }

  function cancelForm() {
    setShowCreate(false);
    setEditingId(null);
    setFormError(null);
    setShowAdvanced(false);
  }

  async function handleSubmit() {
    const error = validate(form);
    if (error) { setFormError(error); return; }
    setFormError(null);

    if (editingId !== null) {
      await updatePreset.mutateAsync({ id: editingId, ...formToPayload(form) });
      setEditingId(null);
    } else {
      await createPreset.mutateAsync(formToPayload(form));
      setShowCreate(false);
    }
  }

  async function handleDelete(id: number) {
    await deletePreset.mutateAsync(id);
    setConfirmDeleteId(null);
  }

  function setField(key: keyof PresetFormData, value: string | boolean) {
    setForm(prev => ({ ...prev, [key]: value }));
  }

  function togglePropertyType(val: string) {
    setForm(prev => {
      const types = prev.property_types.includes(val)
        ? prev.property_types.filter(t => t !== val)
        : [...prev.property_types, val];
      return { ...prev, property_types: types };
    });
  }

  const inputCls = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white";
  const labelCls = "text-xs text-gray-500 mb-1 block";
  const checkboxRowCls = "flex items-center gap-1.5 text-sm text-gray-700";

  function PresetForm({ title }: { title: string }) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 space-y-3">
        <div className="text-sm font-semibold text-gray-800">{title}</div>

        <div>
          <label className={labelCls}>Name *</label>
          <input className={inputCls} value={form.name} onChange={e => setField('name', e.target.value)} placeholder="e.g. Tel Aviv 3-4 rooms" />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className={labelCls}>Source</label>
            <select className={inputCls} value={form.source} onChange={e => setField('source', e.target.value)}>
              <option value="yad2">Yad2</option>
              <option value="madlan">Madlan</option>
              <option value="both">Both</option>
            </select>
          </div>
          {!category && (
            <div>
              <label className={labelCls}>Category</label>
              <select className={inputCls} value={form.category} onChange={e => setField('category', e.target.value)}>
                <option value="rent">Rent</option>
                <option value="forsale">For Sale</option>
              </select>
            </div>
          )}
        </div>

        <div>
          <label className={labelCls}>City code *</label>
          <input className={inputCls} value={form.city_code} onChange={e => setField('city_code', e.target.value)} placeholder="e.g. 5000" />
        </div>

        {form.source === 'madlan' && (
          <div>
            <label className={labelCls}>Madlan city (if different)</label>
            <input className={inputCls} value={form.madlan_city} onChange={e => setField('madlan_city', e.target.value)} placeholder="Leave blank to use city code" />
          </div>
        )}

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className={labelCls}>Min price (₪)</label>
            <input type="number" className={inputCls} value={form.min_price} onChange={e => setField('min_price', e.target.value)} placeholder="0" />
          </div>
          <div>
            <label className={labelCls}>Max price (₪)</label>
            <input type="number" className={inputCls} value={form.max_price} onChange={e => setField('max_price', e.target.value)} placeholder="50000" />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className={labelCls}>Min rooms</label>
            <input type="number" step="0.5" className={inputCls} value={form.min_rooms} onChange={e => setField('min_rooms', e.target.value)} placeholder="1" />
          </div>
          <div>
            <label className={labelCls}>Max rooms</label>
            <input type="number" step="0.5" className={inputCls} value={form.max_rooms} onChange={e => setField('max_rooms', e.target.value)} placeholder="6" />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="form-is-active"
            checked={form.is_active}
            onChange={e => setField('is_active', e.target.checked)}
            className="h-4 w-4"
          />
          <label htmlFor="form-is-active" className="text-sm text-gray-700">Active (runs on scheduled scans)</label>
        </div>

        {/* Advanced filters toggle */}
        <button
          type="button"
          onClick={() => setShowAdvanced(v => !v)}
          className="w-full text-left text-xs text-blue-600 hover:text-blue-800 py-1 flex items-center gap-1"
        >
          <span>{showAdvanced ? '▲ Hide advanced filters' : '▼ Show advanced filters'}</span>
        </button>

        {showAdvanced && (
          <div className="space-y-4 border-t border-gray-200 pt-3">
            {/* Location */}
            <div>
              <div className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">Location</div>
              <div className="mb-2">
                <label className={labelCls}>Area code</label>
                <input className={inputCls} value={form.area_code} onChange={e => setField('area_code', e.target.value)} placeholder="e.g. 2" />
              </div>
              {/* Neighborhood checkbox picker */}
              {(() => {
                const selectedHoods = new Set(
                  form.neighborhood?.split(',').filter(Boolean).map(Number) || []
                );
                return (
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">Neighborhoods</label>
                    {selectedHoods.size > 0 && (
                      <div className="text-xs text-gray-500 mb-1">{selectedHoods.size} selected</div>
                    )}
                    <div className="max-h-48 overflow-y-auto border rounded-lg p-2 space-y-1">
                      {(hoodData?.neighborhoods || []).map(h => {
                        const isChecked = selectedHoods.has(h.hood_id);
                        return (
                          <label key={h.hood_id} className="flex items-center gap-2 text-sm cursor-pointer hover:bg-gray-50 px-1 py-0.5 rounded">
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
                              className="rounded"
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

            {/* Property types */}
            <div>
              <div className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">Property Type</div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
                {PROPERTY_TYPE_OPTIONS.map(opt => (
                  <label key={opt.value} className={checkboxRowCls}>
                    <input
                      type="checkbox"
                      checked={form.property_types.includes(opt.value)}
                      onChange={() => togglePropertyType(opt.value)}
                      className="h-4 w-4 shrink-0"
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
            </div>

            {/* Size */}
            <div>
              <div className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">Size</div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className={labelCls}>Min sqm</label>
                  <input type="number" className={inputCls} value={form.min_sqm} onChange={e => setField('min_sqm', e.target.value)} placeholder="0" />
                </div>
                <div>
                  <label className={labelCls}>Max sqm</label>
                  <input type="number" className={inputCls} value={form.max_sqm} onChange={e => setField('max_sqm', e.target.value)} placeholder="200" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 mt-2">
                <div>
                  <label className={labelCls}>Min floor</label>
                  <input type="number" className={inputCls} value={form.min_floor} onChange={e => setField('min_floor', e.target.value)} placeholder="0" />
                </div>
                <div>
                  <label className={labelCls}>Max floor</label>
                  <input type="number" className={inputCls} value={form.max_floor} onChange={e => setField('max_floor', e.target.value)} placeholder="20" />
                </div>
              </div>
            </div>

            {/* Move-in */}
            <div>
              <div className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">Move-in</div>
              <div>
                <label className={labelCls}>Enter date (available from)</label>
                <input type="date" className={inputCls} value={form.enter_date} onChange={e => setField('enter_date', e.target.value)} />
              </div>
            </div>

            {/* Amenities */}
            <div>
              <div className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">Amenities</div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
                {[
                  { key: 'parking' as const, label: 'Parking' },
                  { key: 'elevator' as const, label: 'Elevator' },
                  { key: 'air_conditioning' as const, label: 'A/C' },
                  { key: 'balcony' as const, label: 'Balcony' },
                  { key: 'pets' as const, label: 'Pets allowed' },
                  { key: 'furniture' as const, label: 'Furnished' },
                  { key: 'mamad' as const, label: 'Safe room (mamad)' },
                  { key: 'accessible' as const, label: 'Accessible' },
                ].map(({ key, label }) => (
                  <label key={key} className={checkboxRowCls}>
                    <input
                      type="checkbox"
                      checked={form[key] as boolean}
                      onChange={e => setField(key, e.target.checked)}
                      className="h-4 w-4 shrink-0"
                    />
                    {label}
                  </label>
                ))}
              </div>
            </div>

            {/* Other */}
            <div>
              <div className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">Other</div>
              <label className={checkboxRowCls}>
                <input
                  type="checkbox"
                  checked={form.img_only}
                  onChange={e => setField('img_only', e.target.checked)}
                  className="h-4 w-4 shrink-0"
                />
                Photos only
              </label>
            </div>

            {/* Property condition */}
            <div>
              <div className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">Property Condition</div>
              <select className={inputCls} value={form.property_condition} onChange={e => setField('property_condition', e.target.value)}>
                <option value="">Any condition</option>
                <option value="1">New from contractor</option>
                <option value="2">New</option>
                <option value="3">Renovated</option>
                <option value="4">Well maintained</option>
                <option value="5">Needs renovation</option>
                <option value="6">For preservation</option>
              </select>
            </div>
          </div>
        )}

        {formError && (
          <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{formError}</div>
        )}

        <div className="flex gap-2">
          <button
            onClick={handleSubmit}
            disabled={createPreset.isPending || updatePreset.isPending}
            className="flex-1 bg-gray-900 text-white rounded-lg py-2 text-sm font-medium disabled:opacity-50"
          >
            {createPreset.isPending || updatePreset.isPending ? 'Saving…' : 'Save'}
          </button>
          <button onClick={cancelForm} className="flex-1 border border-gray-300 rounded-lg py-2 text-sm text-gray-700">
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-[60] flex flex-col bg-white">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 shrink-0">
        <h2 className="text-lg font-bold text-gray-900">Manage Presets</h2>
        <button onClick={onClose} className="p-2 text-gray-500 hover:text-gray-800 text-lg">&#x2715;</button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-4 pt-4 pb-16 space-y-3">

        {/* Add preset button */}
        {!showCreate && editingId === null && (
          <button
            onClick={startCreate}
            className="w-full border-2 border-dashed border-gray-300 rounded-xl py-3 text-sm text-gray-500 hover:border-gray-400 hover:text-gray-700 transition-colors"
          >
            + Add Preset
          </button>
        )}

        {/* Create form */}
        {showCreate && <PresetForm title="New Preset" />}

        {isLoading && (
          <div className="text-center text-gray-400 py-8">Loading…</div>
        )}

        {!isLoading && presets.length === 0 && !showCreate && (
          <div className="text-center text-gray-400 py-8">No presets yet.</div>
        )}

        {/* Preset list */}
        {presets.map(preset => {
          const id = preset.id as number;
          const isEditing = editingId === id;

          if (isEditing) {
            return (
              <div key={id}>
                <PresetForm title={`Editing: ${preset.name as string}`} />
              </div>
            );
          }

          const isActive = preset.is_active as boolean;
          const priceRange = formatPriceRange(preset.min_price, preset.max_price);
          const roomsRange = formatRoomsRange(preset.min_rooms, preset.max_rooms);
          const src = sourceLabel(preset);

          // Neighborhood display — resolve names from hoodData when city matches
          const hoodStr = preset.neighborhood as string | null;
          const hoodIds = hoodStr && hoodStr.trim()
            ? hoodStr.split(',').filter(s => s.trim()).map(Number).filter(n => !isNaN(n))
            : [];
          let hoodLabel = 'All neighborhoods';
          if (hoodIds.length > 0) {
            const hoodMap = new Map((hoodData?.neighborhoods || []).map(h => [h.hood_id, h.neighborhood]));
            const resolvedNames = hoodIds.map(id => hoodMap.get(id)).filter(Boolean) as string[];
            if (resolvedNames.length > 0) {
              const shown = resolvedNames.slice(0, 2).join(', ');
              const extra = resolvedNames.length > 2 ? ` +${resolvedNames.length - 2} more` : '';
              hoodLabel = shown + extra;
            } else {
              hoodLabel = `${hoodIds.length} neighborhood${hoodIds.length > 1 ? 's' : ''}`;
            }
          }

          // Property types
          const propTypes = preset.property_types as string[] | null;
          const propTypesLabel = propTypes && propTypes.length > 0
            ? propTypes.map(t => PROPERTY_TYPE_OPTIONS.find(o => o.value === t)?.label ?? t).join(', ')
            : null;

          const meta = [priceRange, roomsRange, src].filter(Boolean).join(' · ');

          return (
            <div key={id} className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
              <div className="flex items-center gap-3">
                {/* Toggle */}
                <button
                  onClick={() => togglePreset.mutate(id)}
                  className={`shrink-0 w-10 h-6 rounded-full transition-colors ${isActive ? 'bg-green-500' : 'bg-gray-300'}`}
                  title={isActive ? 'Active — click to deactivate' : 'Inactive — click to activate'}
                >
                  <span className={`block w-4 h-4 bg-white rounded-full shadow mx-1 transition-transform ${isActive ? 'translate-x-4' : 'translate-x-0'}`} />
                </button>

                {/* Name + meta */}
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm text-gray-900 truncate">{preset.name as string}</div>
                  {meta && <div className="text-xs text-gray-500 mt-0.5">{meta}</div>}
                  <div className="text-xs text-gray-400 mt-0.5">{hoodLabel}{propTypesLabel ? ` · ${propTypesLabel}` : ''}</div>
                </div>

                {/* Edit / Delete / Clone / Run Now */}
                <div className="flex gap-1 shrink-0">
                  <button
                    onClick={() => startEdit(preset)}
                    className="px-2 py-1 text-xs rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50"
                  >Edit</button>
                  <button
                    onClick={() => setConfirmDeleteId(id)}
                    className="px-2 py-1 text-xs rounded-lg border border-red-200 text-red-600 hover:bg-red-50"
                  >Delete</button>
                  <button
                    onClick={() => clonePreset.mutate(id)}
                    disabled={clonePreset.isPending}
                    className="px-2 py-1 text-xs rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50"
                  >Clone</button>
                  {isActive && (
                    <button
                      onClick={() => scanPreset.mutate(id)}
                      disabled={scanPreset.isPending}
                      className="px-2 py-1 text-xs rounded-lg border border-blue-200 text-blue-600 hover:bg-blue-50"
                    >{scanPreset.isPending ? 'Scanning...' : 'Run Now'}</button>
                  )}
                </div>
              </div>

              {/* Active badge */}
              <div className="mt-2">
                <span className={`inline-block px-2 py-0.5 text-xs rounded-full font-medium ${
                  isActive ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                }`}>
                  {isActive ? 'Active' : 'Inactive'}
                </span>
              </div>

              {/* Delete confirmation */}
              {confirmDeleteId === id && (
                <div className="mt-3 bg-red-50 border border-red-200 rounded-lg p-3 space-y-2">
                  <p className="text-sm text-red-700">Delete this preset? Properties found by this preset will be kept.</p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleDelete(id)}
                      disabled={deletePreset.isPending}
                      className="flex-1 bg-red-600 text-white rounded-lg py-1.5 text-sm font-medium disabled:opacity-50"
                    >
                      {deletePreset.isPending ? 'Deleting…' : 'Yes, delete'}
                    </button>
                    <button
                      onClick={() => setConfirmDeleteId(null)}
                      className="flex-1 border border-gray-300 rounded-lg py-1.5 text-sm text-gray-700"
                    >Cancel</button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
