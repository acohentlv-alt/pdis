import { useQuery } from '@tanstack/react-query';
import { apiFetch } from './client';

export function usePresetStats(category?: string) {
  const url = category ? `/api/presets/stats/latest?category=${category}` : '/api/presets/stats/latest';
  return useQuery({
    queryKey: ['presetStats', category],
    queryFn: () => apiFetch<{ presets: Record<string, unknown>[] }>(url),
  });
}

export function useProperty(yad2Id: string | undefined) {
  return useQuery({
    queryKey: ['property', yad2Id],
    queryFn: () => apiFetch<Record<string, unknown>>(`/api/properties/${yad2Id}`),
    enabled: !!yad2Id,
  });
}

export function useSignals(yad2Id: string | undefined) {
  return useQuery({
    queryKey: ['signals', yad2Id],
    queryFn: () => apiFetch<Record<string, unknown>>(`/api/properties/${yad2Id}/signals`),
    enabled: !!yad2Id,
  });
}

export function useEvents(yad2Id: string | undefined) {
  return useQuery({
    queryKey: ['events', yad2Id],
    queryFn: () => apiFetch<{ events: Record<string, unknown>[] }>(`/api/properties/${yad2Id}/events`),
    enabled: !!yad2Id,
  });
}

export function useOperatorInput(yad2Id: string | undefined) {
  return useQuery({
    queryKey: ['operatorInput', yad2Id],
    queryFn: () => apiFetch<Record<string, unknown>>(`/api/properties/${yad2Id}/operator-input`),
    enabled: !!yad2Id,
  });
}

export function useMatches(yad2Id: string | undefined) {
  return useQuery({
    queryKey: ['matches', yad2Id],
    queryFn: () => apiFetch<{ matches: Record<string, unknown>[] }>(`/api/properties/${yad2Id}/matches`),
    enabled: !!yad2Id,
  });
}

export function useClosedComps(yad2Id: string | undefined) {
  return useQuery({
    queryKey: ['closedComps', yad2Id],
    queryFn: () => apiFetch<{
      median_pps: number | null;
      count: number;
      source_level: 'building' | 'street' | 'neighborhood' | 'none';
      deals: Array<{
        deal_id: string;
        deal_date: string;
        floor: number | null;
        sqm: number | null;
        sale_price: number;
        price_per_sqm: number | null;
      }>;
    }>(`/api/properties/${yad2Id}/comps`),
    enabled: !!yad2Id,
  });
}

export function useAllPresets() {
  return useQuery({
    queryKey: ['presets', 'all'],
    queryFn: () => apiFetch<{ presets: Record<string, unknown>[] }>('/api/presets'),
  });
}

export function useFbGroups() {
  return useQuery({
    queryKey: ['fbGroups'],
    queryFn: () => apiFetch<{ groups: Array<{ group_id: string; name: string; url: string; is_active: boolean }> }>('/api/fb-groups'),
  });
}


export interface CustomSearchCriteria {
  city_code?: string;
  category?: string;
  min_price?: number;
  max_price?: number;
  min_rooms?: number;
  max_rooms?: number;
}

export function useCustomSearch(criteria: CustomSearchCriteria | null) {
  return useQuery({
    queryKey: ['customSearch', JSON.stringify(criteria)],
    queryFn: () => {
      const params = new URLSearchParams();
      if (criteria?.city_code) params.set('city_code', criteria.city_code);
      if (criteria?.category) params.set('category', criteria.category);
      if (criteria?.min_price != null) params.set('min_price', String(criteria.min_price));
      if (criteria?.max_price != null) params.set('max_price', String(criteria.max_price));
      if (criteria?.min_rooms != null) params.set('min_rooms', String(criteria.min_rooms));
      if (criteria?.max_rooms != null) params.set('max_rooms', String(criteria.max_rooms));
      params.set('per_page', '2000');
      return apiFetch<{ total: number; properties: Record<string, unknown>[] }>(
        `/api/search/custom?${params}`
      );
    },
    enabled: criteria !== null,
  });
}

export function usePresetProperties(presetId: number | null) {
  return useQuery({
    queryKey: ['presetProperties', presetId],
    queryFn: () => apiFetch<{ total: number; properties: Record<string, unknown>[] }>(
      `/api/presets/${presetId}/properties?per_page=2000`
    ),
    enabled: presetId !== null && presetId > 0,
  });
}

export function useAmitFitProperties(enabled: boolean) {
  return useQuery({
    queryKey: ['amitFitProperties'],
    queryFn: () => apiFetch<{ total: number; properties: Record<string, unknown>[] }>(
      '/api/amit-fit/properties?per_page=2000'
    ),
    enabled,
  });
}

export function usePropertiesByPreset(presetId: number | null) {
  return useQuery({
    queryKey: ['propertiesByPreset', presetId],
    queryFn: () => apiFetch<{ total: number; properties: Record<string, unknown>[] }>(
      `/api/properties?preset_id=${presetId}&per_page=500`
    ),
    enabled: presetId !== null,
  });
}

export function useFavoriteIds() {
  return useQuery({
    queryKey: ['favoriteIds'],
    queryFn: () => apiFetch<{ ids: string[] }>('/api/favorites/ids'),
  });
}

export function useFavorites() {
  return useQuery({
    queryKey: ['favorites'],
    queryFn: () => apiFetch<{ total: number; favorites: Record<string, unknown>[] }>('/api/favorites'),
  });
}

export function usePropertiesByEvent(eventType: string | null, category?: string) {
  const params = new URLSearchParams();
  if (eventType) params.set('event_type', eventType);
  if (category) params.set('category', category);
  return useQuery({
    queryKey: ['properties', 'by-event', eventType, category],
    queryFn: () => apiFetch<{ properties: Record<string, unknown>[] }>(`/api/events/properties?${params}`),
    enabled: !!eventType,
  });
}

export function useWhitelistIds() {
  return useQuery({
    queryKey: ['whitelistIds'],
    queryFn: () => apiFetch<{ ids: string[] }>('/api/whitelist/ids'),
  });
}

export function useBlacklistIds() {
  return useQuery({
    queryKey: ['blacklistIds'],
    queryFn: () => apiFetch<{ ids: string[] }>('/api/blacklist/ids'),
  });
}

export function useWhitelistProperties() {
  return useQuery({
    queryKey: ['whitelistProperties'],
    queryFn: () => apiFetch<{ total: number; properties: Record<string, unknown>[] }>('/api/whitelist'),
  });
}

export function useBlacklistProperties() {
  return useQuery({
    queryKey: ['blacklistProperties'],
    queryFn: () => apiFetch<{ total: number; properties: Record<string, unknown>[] }>('/api/blacklist'),
  });
}

export function usePropertySearch(query: string, category?: string) {
  const params = new URLSearchParams({ q: query });
  if (category) params.set('category', category);
  return useQuery({
    queryKey: ['propertySearch', query, category],
    queryFn: () => apiFetch<{ properties: Record<string, unknown>[] }>(`/api/properties/search?${params}`),
    enabled: query.length >= 2,
  });
}

export function useScanStatus() {
  return useQuery({
    queryKey: ['scanStatus'],
    queryFn: () => apiFetch<{ running: boolean; progress: number | null }>('/api/scan/status'),
    refetchInterval: (query) => query.state.data?.running ? 1500 : 10000,
  });
}

export function usePresetLastSession(presetId: number | null, enabled: boolean) {
  return useQuery({
    queryKey: ['presetLastSession', presetId],
    queryFn: () => apiFetch<{
      session: null | {
        session_id: number;
        started_at: string;
        finished_at: string | null;
        status: 'running' | 'done' | 'error' | 'blocked';
        listings_found: number | null;
        new_listings: number | null;
        error_message: string | null;
        progress: number | null;
      };
    }>(`/api/presets/${presetId}/last-session`),
    enabled: presetId !== null,
    refetchInterval: enabled ? 2000 : false,
  });
}

export function useNeighborhoods(cityCode: string | null) {
  return useQuery({
    queryKey: ['neighborhoods', cityCode],
    queryFn: () => apiFetch<{ neighborhoods: { hood_id: number; neighborhood: string; listing_count: number }[] }>(
      `/api/neighborhoods?city_code=${cityCode}`
    ),
    enabled: cityCode !== null && cityCode !== '',
  });
}

export function useThresholds(category: string = 'forsale', enabled: boolean = true) {
  return useQuery({
    queryKey: ['thresholds', category],
    queryFn: () => apiFetch<{ thresholds: Array<{
      id: number; neighborhood: string; hood_id: number | null;
      category: string; size_min: number; size_max: number;
      target_price_per_sqm_preferred: number; target_price_per_sqm_max: number;
    }> }>(`/api/thresholds?category=${category}`),
    enabled,
    refetchOnWindowFocus: false,
  });
}

export interface FeatureAdjustmentRow {
  id: number;
  neighborhood: string;
  hood_id: number | null;
  category: string;
  year_old_pref_pct: number;
  year_old_max_pct: number;
  year_mid_old_pref_pct: number;
  year_mid_old_max_pct: number;
  year_mid_pref_pct: number;
  year_mid_max_pct: number;
  year_new_pref_pct: number;
  year_new_max_pct: number;
  walkup_pct_per_floor: number;
  parking_bonus_pref: number;
  parking_bonus_max: number;
  mamad_pct_pref: number;
  mamad_pct_max: number;
  created_at: string;
  updated_at: string;
}

export function useFeatureAdjustments(category: string = 'forsale', enabled: boolean = true) {
  return useQuery({
    queryKey: ['featureAdjustments', category],
    queryFn: () => apiFetch<{ adjustments: FeatureAdjustmentRow[] }>(
      `/api/feature-adjustments?category=${category}`
    ),
    enabled,
    refetchOnWindowFocus: false,
  });
}
