// Shared types, constants, and pure utilities for PresetManager

export interface PresetFormData {
  name: string;
  source: string;
  city_code: string;
  madlan_city: string;
  min_price: string;
  max_price: string;
  min_rooms: string;
  max_rooms: string;
  scan_enabled: boolean;
  is_visible: boolean;
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
  fb_groups: string[];
}

export const PROPERTY_TYPE_OPTIONS = [
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

export const SIZE_BUCKETS: Array<[number, number]> = [
  [30, 40], [40, 50], [50, 60], [60, 70], [70, 80], [80, 90], [90, 100],
];

export const bucketKey = (lo: number, hi: number) => `${lo}-${hi}`;

export interface FaRow {
  year_old_pref: string;     year_old_max: string;
  year_mid_old_pref: string; year_mid_old_max: string;
  year_mid_pref: string;     year_mid_max: string;
  year_new_pref: string;     year_new_max: string;
  walkup: string;
  parking_pref: string; parking_max: string;
  mamad_pref: string;   mamad_max: string;
}

export const _DEFAULT_FA: FaRow = {
  year_old_pref: '-18',     year_old_max: '-18',
  year_mid_old_pref: '-8',  year_mid_old_max: '-8',
  year_mid_pref: '0',       year_mid_max: '0',
  year_new_pref: '5',       year_new_max: '5',
  walkup: '3',
  parking_pref: '0', parking_max: '0',
  mamad_pref: '0',   mamad_max: '0',
};

export type FaState = Record<number, FaRow>;

export type PricingRow = { pref: string; max: string };
export type PricingState = Record<number, Record<string, PricingRow>>;

export function emptyForm(): PresetFormData {
  return {
    name: '',
    source: 'yad2',
    city_code: '',
    madlan_city: '',
    min_price: '',
    max_price: '',
    min_rooms: '',
    max_rooms: '',
    scan_enabled: true,
    is_visible: true,
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
    fb_groups: [] as string[],
  };
}

export function validate(form: PresetFormData): string | null {
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

export function formToPayload(form: PresetFormData): Record<string, unknown> {
  return {
    name: form.name.trim(),
    source: form.source,
    city_code: form.city_code.trim(),
    madlan_city: form.madlan_city.trim() || form.city_code.trim(),
    min_price: form.min_price !== '' ? Number(form.min_price) : null,
    max_price: form.max_price !== '' ? Number(form.max_price) : null,
    min_rooms: form.min_rooms !== '' ? Number(form.min_rooms) : null,
    max_rooms: form.max_rooms !== '' ? Number(form.max_rooms) : null,
    scan_enabled: form.scan_enabled,
    is_visible: form.is_visible,
    category: form.category,
    // Advanced filters
    area_code: form.area_code.trim() || null,
    neighborhood: form.neighborhood.trim() || null,
    property_types: form.property_types.length > 0 ? form.property_types : null,
    fb_groups: form.fb_groups.length > 0 ? form.fb_groups : null,
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

export function presetToForm(preset: Record<string, unknown>): PresetFormData {
  const extra = (preset.extra_params ?? {}) as Record<string, unknown>;
  const VALID_SOURCES = new Set([
    'yad2', 'madlan', 'facebook',
    'yad2_madlan', 'yad2_facebook', 'madlan_facebook', 'all',
  ]);
  const rawSrc = extra.source as string | undefined;
  const normalized = rawSrc === 'both' ? 'yad2_madlan' : rawSrc;
  const source = normalized && VALID_SOURCES.has(normalized) ? normalized : 'yad2';

  return {
    name: (preset.name as string) ?? '',
    source,
    city_code: (preset.city_code as string) ?? '',
    madlan_city: (extra.madlan_city as string) ?? '',
    min_price: preset.min_price != null ? String(preset.min_price) : '',
    max_price: preset.max_price != null ? String(preset.max_price) : '',
    min_rooms: preset.min_rooms != null ? String(preset.min_rooms) : '',
    max_rooms: preset.max_rooms != null ? String(preset.max_rooms) : '',
    scan_enabled: (preset.scan_enabled as boolean) ?? true,
    is_visible:   (preset.is_visible as boolean)   ?? true,
    category: (preset.category as string) ?? 'rent',
    // Advanced filters — from DB columns
    area_code: (preset.area_code as string) ?? '',
    neighborhood: (preset.neighborhood as string) ?? '',
    property_types: (preset.property_types as string[]) ?? [],
    fb_groups: Array.isArray(extra.fb_groups) ? (extra.fb_groups as string[]) : [],
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

export function formatPriceRange(min: unknown, max: unknown): string {
  if (!min && !max) return '';
  const parts: string[] = [];
  if (min != null) parts.push(`${Number(min).toLocaleString('he-IL')} ₪`);
  if (max != null) parts.push(`${Number(max).toLocaleString('he-IL')} ₪`);
  return parts.join(' – ');
}

export function formatRoomsRange(min: unknown, max: unknown): string {
  if (min == null && max == null) return '';
  if (min != null && max != null) return `${min}–${max} rooms`;
  if (min != null) return `${min}+ rooms`;
  return `up to ${max} rooms`;
}

export function sourceLabel(preset: Record<string, unknown>): string {
  const extra = (preset.extra_params ?? {}) as Record<string, unknown>;
  const src = extra.source as string | undefined;
  switch (src) {
    case 'madlan': return 'Madlan';
    case 'facebook': return 'Facebook';
    case 'both': return 'Yad2 + Madlan';
    case 'yad2_madlan': return 'Yad2 + Madlan';
    case 'yad2_facebook': return 'Yad2 + Facebook';
    case 'madlan_facebook': return 'Madlan + Facebook';
    case 'all': return 'Yad2 + Madlan + Facebook';
    default: return 'Yad2';
  }
}

export function formatTimeAgo(isoString: string | null | undefined): string {
  if (!isoString) return 'unknown';
  const diffMs = Date.now() - new Date(isoString).getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return 'just now';
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return `${Math.floor(diffHr / 24)}d ago`;
}

// Design tokens (matching FilterDrawer)
export const inputClass = 'border border-gray-200 rounded-xl px-4 py-3 text-[15px] bg-gray-50 min-h-[48px] focus:bg-white focus:border-gray-900 focus:outline-none focus:ring-2 focus:ring-gray-900/10 transition-all placeholder:text-gray-400';
export const chipBase = 'px-4 py-2.5 text-sm rounded-full border transition-all whitespace-nowrap min-h-[44px] flex items-center font-medium';
export const chipActive = 'bg-gray-900 text-white border-gray-900 shadow-sm';
export const chipInactive = 'bg-white text-gray-700 border-gray-200 hover:border-gray-400';
export const sectionLabel = 'text-[11px] uppercase tracking-[0.08em] font-semibold text-gray-500 mb-3';
export const sectionCard = 'bg-gray-50 rounded-2xl p-4';
export const primaryCta = 'bg-gray-900 hover:bg-gray-800 active:bg-gray-700 text-white rounded-2xl py-4 text-base font-semibold transition-colors shadow-lg shadow-gray-900/20';

// Advanced filters auto-open predicate
export function hasAdvancedFilters(form: PresetFormData): boolean {
  return (
    form.area_code.trim() !== '' ||
    form.neighborhood.trim() !== '' ||
    form.property_types.length > 0 ||
    form.min_sqm.trim() !== '' ||
    form.max_sqm.trim() !== '' ||
    form.min_floor.trim() !== '' ||
    form.max_floor.trim() !== '' ||
    form.enter_date.trim() !== '' ||
    form.img_only ||
    form.parking ||
    form.elevator ||
    form.air_conditioning ||
    form.balcony ||
    form.pets ||
    form.furniture ||
    form.mamad ||
    form.accessible ||
    form.property_condition.trim() !== '' ||
    form.fb_groups.length > 0
  );
}
