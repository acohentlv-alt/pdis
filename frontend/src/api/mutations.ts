import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from './client';

export function useAddNote(yad2Id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { note: string; created_by?: string }) =>
      apiFetch(`/api/properties/${yad2Id}/notes`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['property', yad2Id] });
    },
  });
}

export function useDeleteNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ noteId, yad2Id }: { noteId: number; yad2Id: string }) =>
      apiFetch(`/api/notes/${noteId}`, { method: 'DELETE' }).then(() => ({ yad2Id })),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ['property', variables.yad2Id] });
    },
  });
}

export function useWhitelist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (yad2Id: string) =>
      apiFetch(`/api/whitelist/${yad2Id}`, { method: 'POST', body: JSON.stringify({}) }),
    onSuccess: (_data, yad2Id) => {
      qc.invalidateQueries({ queryKey: ['property', yad2Id] });
      qc.invalidateQueries({ queryKey: ['whitelistIds'] });
      qc.invalidateQueries({ queryKey: ['whitelistProperties'] });
    },
  });
}

export function useRemoveWhitelist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (yad2Id: string) => apiFetch(`/api/whitelist/${yad2Id}`, { method: 'DELETE' }),
    onSuccess: (_data, yad2Id) => {
      qc.invalidateQueries({ queryKey: ['property', yad2Id] });
      qc.invalidateQueries({ queryKey: ['whitelistIds'] });
      qc.invalidateQueries({ queryKey: ['whitelistProperties'] });
    },
  });
}

export function useBlacklist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (yad2Id: string) =>
      apiFetch(`/api/blacklist/${yad2Id}`, { method: 'POST', body: JSON.stringify({}) }),
    onSuccess: (_data, yad2Id) => {
      qc.invalidateQueries({ queryKey: ['property', yad2Id] });
      qc.invalidateQueries({ queryKey: ['blacklistIds'] });
      qc.invalidateQueries({ queryKey: ['blacklistProperties'] });
      qc.invalidateQueries({ queryKey: ['amitFitProperties'] });
    },
  });
}

export function useRemoveBlacklist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (yad2Id: string) => apiFetch(`/api/blacklist/${yad2Id}`, { method: 'DELETE' }),
    onSuccess: (_data, yad2Id) => {
      qc.invalidateQueries({ queryKey: ['property', yad2Id] });
      qc.invalidateQueries({ queryKey: ['blacklistIds'] });
      qc.invalidateQueries({ queryKey: ['blacklistProperties'] });
      qc.invalidateQueries({ queryKey: ['amitFitProperties'] });
    },
  });
}


export function useAddFavorite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (yad2Id: string) => apiFetch(`/api/favorites/${yad2Id}`, { method: 'POST' }),
    onSuccess: (_data, yad2Id) => {
      queryClient.invalidateQueries({ queryKey: ['favoriteIds'] });
      queryClient.invalidateQueries({ queryKey: ['favorites'] });
      queryClient.invalidateQueries({ queryKey: ['property', yad2Id] });
    },
  });
}

export function useRemoveFavorite() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (yad2Id: string) => apiFetch(`/api/favorites/${yad2Id}`, { method: 'DELETE' }),
    onSuccess: (_data, yad2Id) => {
      queryClient.invalidateQueries({ queryKey: ['favoriteIds'] });
      queryClient.invalidateQueries({ queryKey: ['favorites'] });
      queryClient.invalidateQueries({ queryKey: ['property', yad2Id] });
    },
  });
}

export function useCreatePreset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      apiFetch('/api/presets', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['presets'] });
      qc.invalidateQueries({ queryKey: ['amitFitProperties'] });
    },
  });
}

export function useUpdatePreset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: Record<string, unknown>) =>
      apiFetch(`/api/presets/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['presets'] });
      qc.invalidateQueries({ queryKey: ['amitFitProperties'] });
    },
  });
}

export function useDeletePreset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/api/presets/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['presets'] });
      qc.invalidateQueries({ queryKey: ['amitFitProperties'] });
    },
  });
}

export function useTogglePreset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/api/presets/${id}/toggle`, { method: 'PATCH' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['presets'] });
      qc.invalidateQueries({ queryKey: ['amitFitProperties'] });
    },
  });
}

export function useClonePreset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/api/presets/${id}/clone`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['presets'] }),
  });
}

export function useScanPreset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/api/scan/${id}`, { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['presets'] });
      qc.invalidateQueries({ queryKey: ['presetProperties'] });
      qc.invalidateQueries({ queryKey: ['presetStats'] });
      qc.invalidateQueries({ queryKey: ['amitFitProperties'] });
      qc.invalidateQueries({ queryKey: ['closedComps'] });
    },
  });
}

export function useSaveOperatorInput(yad2Id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      agent_name?: string | null;
      manual_days_on_market?: number | null;
      flexibility?: string | null;
      condition?: string | null;
    }) =>
      apiFetch(`/api/properties/${yad2Id}/operator-input`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['operatorInput', yad2Id] });
    },
  });
}

export function useUpsertThresholds() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (thresholds: Array<{
      neighborhood: string; hood_id?: number | null; category: string;
      size_min: number; size_max: number;
      target_price_per_sqm_preferred: number; target_price_per_sqm_max: number;
    }>) => apiFetch('/api/thresholds', {
      method: 'PUT',
      body: JSON.stringify({ thresholds }),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['thresholds'] });
      qc.invalidateQueries({ queryKey: ['amitFitProperties'] });
    },
  });
}

export function useUpsertFeatureAdjustments() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (adjustments: Array<{
      neighborhood: string; hood_id?: number | null; category: string;
      year_old_pref_pct: number; year_old_max_pct: number;
      year_mid_old_pref_pct: number; year_mid_old_max_pct: number;
      year_mid_pref_pct: number; year_mid_max_pct: number;
      year_new_pref_pct: number; year_new_max_pct: number;
      walkup_pct_per_floor: number;
      parking_bonus_pref: number; parking_bonus_max: number;
      mamad_pct_pref: number; mamad_pct_max: number;
    }>) => apiFetch('/api/feature-adjustments', {
      method: 'PUT',
      body: JSON.stringify({ adjustments }),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['featureAdjustments'] });
      qc.invalidateQueries({ queryKey: ['amitFitProperties'] });
    },
  });
}
