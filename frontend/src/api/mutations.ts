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
      qc.invalidateQueries({ queryKey: ['opportunities'] });
      qc.invalidateQueries({ queryKey: ['classifications'] });
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
      qc.invalidateQueries({ queryKey: ['opportunities'] });
      qc.invalidateQueries({ queryKey: ['classifications'] });
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
      qc.invalidateQueries({ queryKey: ['opportunities'] });
      qc.invalidateQueries({ queryKey: ['classifications'] });
      qc.invalidateQueries({ queryKey: ['blacklistIds'] });
      qc.invalidateQueries({ queryKey: ['blacklistProperties'] });
    },
  });
}

export function useRemoveBlacklist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (yad2Id: string) => apiFetch(`/api/blacklist/${yad2Id}`, { method: 'DELETE' }),
    onSuccess: (_data, yad2Id) => {
      qc.invalidateQueries({ queryKey: ['property', yad2Id] });
      qc.invalidateQueries({ queryKey: ['opportunities'] });
      qc.invalidateQueries({ queryKey: ['classifications'] });
      qc.invalidateQueries({ queryKey: ['blacklistIds'] });
      qc.invalidateQueries({ queryKey: ['blacklistProperties'] });
    },
  });
}

export function useOpenSearch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: {
      city_code?: string;
      min_price?: number;
      max_price?: number;
      min_rooms?: number;
      max_rooms?: number;
      category?: string;
    }) =>
      apiFetch('/api/scan/open', {
        method: 'POST',
        body: JSON.stringify(params),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['opportunities'] });
      queryClient.invalidateQueries({ queryKey: ['classifications'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
      queryClient.invalidateQueries({ queryKey: ['presetStats'] });
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
    onSuccess: () => qc.invalidateQueries({ queryKey: ['presets'] }),
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
    onSuccess: () => qc.invalidateQueries({ queryKey: ['presets'] }),
  });
}

export function useDeletePreset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/api/presets/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['presets'] }),
  });
}

export function useTogglePreset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/api/presets/${id}/toggle`, { method: 'PATCH' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['presets'] }),
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
