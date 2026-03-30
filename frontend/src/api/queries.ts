import { useQuery } from '@tanstack/react-query';
import { apiFetch } from './client';

export function useStats() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: () => apiFetch<Record<string, unknown>>('/api/stats'),
  });
}

export function usePresetStats() {
  return useQuery({
    queryKey: ['presetStats'],
    queryFn: () => apiFetch<{ presets: Record<string, unknown>[] }>('/api/presets/stats/latest'),
  });
}

export function useOpportunities() {
  return useQuery({
    queryKey: ['opportunities'],
    queryFn: () => apiFetch<{ total: number; opportunities: Record<string, unknown>[] }>('/api/opportunities?per_page=500'),
  });
}

export function useClassifications(classification?: string) {
  const params = new URLSearchParams({ per_page: '500' });
  if (classification) params.set('classification', classification);
  return useQuery({
    queryKey: ['classifications', classification],
    queryFn: () => apiFetch<{ total: number; classifications: Record<string, unknown>[] }>(`/api/classifications?${params}`),
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

export function useOpenSearchPresets() {
  return useQuery({
    queryKey: ['openSearchPresets'],
    queryFn: () => apiFetch<{ presets: Record<string, unknown>[] }>('/api/presets?is_active=false'),
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
