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

export function useWhitelist(yad2Id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch(`/api/whitelist/${yad2Id}`, { method: 'POST', body: JSON.stringify({}) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['property', yad2Id] });
      qc.invalidateQueries({ queryKey: ['opportunities'] });
      qc.invalidateQueries({ queryKey: ['classifications'] });
    },
  });
}

export function useRemoveWhitelist(yad2Id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch(`/api/whitelist/${yad2Id}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['property', yad2Id] });
      qc.invalidateQueries({ queryKey: ['opportunities'] });
      qc.invalidateQueries({ queryKey: ['classifications'] });
    },
  });
}

export function useBlacklist(yad2Id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch(`/api/blacklist/${yad2Id}`, { method: 'POST', body: JSON.stringify({}) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['property', yad2Id] });
      qc.invalidateQueries({ queryKey: ['opportunities'] });
      qc.invalidateQueries({ queryKey: ['classifications'] });
    },
  });
}

export function useRemoveBlacklist(yad2Id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch(`/api/blacklist/${yad2Id}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['property', yad2Id] });
      qc.invalidateQueries({ queryKey: ['opportunities'] });
      qc.invalidateQueries({ queryKey: ['classifications'] });
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
