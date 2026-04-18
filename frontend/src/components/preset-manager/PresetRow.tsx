import { useEffect, useRef } from 'react';
import { usePresetLastSession } from '../../api/queries';
import {
  PROPERTY_TYPE_OPTIONS,
  formatPriceRange,
  formatRoomsRange,
  sourceLabel,
  formatTimeAgo,
} from './presetFormUtils';

interface PresetRowProps {
  preset: Record<string, unknown>;
  editingId: number | null;
  activeScanPresetId: number | null;
  setActiveScanPresetId: (id: number | null) => void;
  scanStatus: { running: boolean; progress: number | null } | undefined;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  scanPreset: any;
  startEdit: (preset: Record<string, unknown>) => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  clonePreset: any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  toggleScanEnabled: any;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  toggleVisibility: any;
  confirmDeleteId: number | null;
  setConfirmDeleteId: (id: number | null) => void;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  deletePreset: any;
  handleDelete: (id: number) => void;
  setScanError: (msg: string | null) => void;
  hoodData: { neighborhoods: { hood_id: number; neighborhood: string; listing_count: number }[] } | undefined;
  openKebabId: number | null;
  setOpenKebabId: (id: number | null) => void;
}

export default function PresetRow({
  preset,
  editingId,
  activeScanPresetId,
  setActiveScanPresetId,
  scanStatus,
  scanPreset,
  startEdit,
  clonePreset,
  toggleScanEnabled,
  toggleVisibility,
  confirmDeleteId,
  setConfirmDeleteId,
  deletePreset,
  handleDelete,
  setScanError,
  hoodData,
  openKebabId,
  setOpenKebabId,
}: PresetRowProps) {
  // HOOK 1: click-outside + ESC handler for kebab menu — MUST be before early return
  const kebabRef = useRef<HTMLDivElement>(null);
  const id = preset?.id as number;
  const isKebabOpen = openKebabId === id;

  useEffect(() => {
    if (!isKebabOpen) return;
    function handleClickOutside(e: MouseEvent) {
      if (kebabRef.current && !kebabRef.current.contains(e.target as Node)) {
        setOpenKebabId(null);
      }
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpenKebabId(null);
    }
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isKebabOpen, setOpenKebabId]);

  // HOOK 2: last session data
  const { data: lastSessionData } = usePresetLastSession(
    id,
    activeScanPresetId === id
  );

  // Early return AFTER hooks
  if (!preset) return null;

  const isEditing = editingId === id;
  // When editing this row, show nothing — the form is rendered in the sheet body by PresetManager
  if (isEditing) return null;

  const scanEnabled = (preset.scan_enabled as boolean) ?? true;
  const isVisible   = (preset.is_visible as boolean)   ?? true;
  const isScanningThis = activeScanPresetId === id;
  const isAnyScanRunning = scanStatus?.running ?? false;
  const progress = isScanningThis ? (scanStatus?.progress ?? null) : null;
  const lastSession = lastSessionData?.session ?? null;

  const priceRange = formatPriceRange(preset.min_price, preset.max_price);
  const roomsRange = formatRoomsRange(preset.min_rooms, preset.max_rooms);
  const src = sourceLabel(preset);

  // Neighborhood display — resolve names from hoodData when city matches
  const hoodStr = preset.neighborhood as string | null;
  const hoodIds = hoodStr && hoodStr.trim()
    ? hoodStr.split(',').filter((s: string) => s.trim()).map(Number).filter((n: number) => !isNaN(n))
    : [];
  let hoodLabel = '';
  if (hoodIds.length > 0) {
    const hoodMap = new Map((hoodData?.neighborhoods || []).map((h) => [h.hood_id, h.neighborhood]));
    const resolvedNames = hoodIds.map((hid: number) => hoodMap.get(hid)).filter(Boolean) as string[];
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
    ? propTypes.map((t: string) => PROPERTY_TYPE_OPTIONS.find(o => o.value === t)?.label ?? t).join(', ')
    : null;

  const metaLine = [priceRange, roomsRange, src].filter(Boolean).join(' · ');
  const detailLine = [hoodLabel, propTypesLabel].filter(Boolean).join(' · ');

  return (
    <div className={`rounded-2xl border p-4 transition-colors ${scanEnabled ? 'bg-white border-gray-200 shadow-sm' : 'bg-gray-50 border-gray-200 opacity-60'}`}>
      <div className="flex items-center gap-3">
        {/* Toggle switch — enlarged hit area 44×44 */}
        <button
          onClick={() => toggleScanEnabled.mutate(id)}
          className={`shrink-0 w-12 h-7 rounded-full transition-colors min-w-[44px] min-h-[44px] flex items-center justify-start px-1 ${scanEnabled ? 'bg-green-500' : 'bg-gray-300'}`}
          title={scanEnabled ? 'Scanning enabled — click to disable' : 'Scanning disabled — click to enable'}
          style={{ padding: '0 2px' }}
        >
          <span className={`block w-5 h-5 bg-white rounded-full shadow transition-transform ${scanEnabled ? 'translate-x-5' : 'translate-x-0'}`} />
        </button>

        {/* Name + meta */}
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-sm text-gray-900 truncate">{preset.name as string}</div>
          {metaLine && <div className="text-xs text-gray-500 mt-0.5">{metaLine}</div>}
          {detailLine && <div className="text-xs text-gray-400 mt-0.5">{detailLine}</div>}
        </div>

        {/* Run Now CTA */}
        {scanEnabled && (
          <button
            onClick={() => {
              setScanError(null);
              setActiveScanPresetId(id);
              scanPreset.mutate(id, {
                onError: (err: unknown) => {
                  setActiveScanPresetId(null);
                  setScanError(err instanceof Error ? err.message : String(err));
                },
              });
            }}
            disabled={isScanningThis || (isAnyScanRunning && !isScanningThis)}
            className="shrink-0 px-3 py-2 text-xs rounded-xl border border-blue-200 text-blue-600 hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed font-medium min-h-[44px]"
          >
            {isScanningThis
              ? `${progress ?? 0}%`
              : isAnyScanRunning
              ? 'Running…'
              : 'Run Now'}
          </button>
        )}

        {/* Kebab menu */}
        <div className="relative shrink-0" ref={kebabRef}>
          <button
            onClick={() => setOpenKebabId(isKebabOpen ? null : id)}
            className="w-[44px] h-[44px] flex items-center justify-center text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-xl transition-colors text-lg"
            aria-label="More options"
          >
            ⋮
          </button>
          {isKebabOpen && (
            <div className="absolute right-0 top-12 bg-white border border-gray-200 rounded-2xl shadow-lg z-20 min-w-[140px] py-1 overflow-hidden">
              <button
                onClick={() => { setOpenKebabId(null); startEdit(preset); }}
                className="w-full text-left px-4 py-3 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Edit
              </button>
              <button
                onClick={() => { setOpenKebabId(null); clonePreset.mutate(id); }}
                disabled={clonePreset.isPending}
                className="w-full text-left px-4 py-3 text-sm text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50"
              >
                Clone
              </button>
              <button
                onClick={() => { setOpenKebabId(null); toggleVisibility.mutate(id); }}
                className="w-full text-left px-4 py-3 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
              >
                {isVisible ? 'Hide from app' : 'Show in app'}
              </button>
              <button
                onClick={() => { setOpenKebabId(null); setConfirmDeleteId(id); }}
                className="w-full text-left px-4 py-3 text-sm text-red-600 hover:bg-red-50 transition-colors"
              >
                Delete
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Last-scan status line */}
      {(() => {
        if (!lastSession) return <div className="text-xs text-gray-500 mt-2">Never scanned</div>;
        const timeAgo = formatTimeAgo(lastSession.finished_at || lastSession.started_at);
        if (lastSession.status === 'done') {
          return <div className="text-xs text-gray-500 mt-2">Last scan: {timeAgo} · {lastSession.listings_found ?? 0} listings</div>;
        }
        if (lastSession.status === 'error') {
          return <div className="text-xs text-red-600 mt-2 flex items-center gap-1"><span className="inline-block w-1.5 h-1.5 rounded-full bg-red-500 shrink-0" />Last scan: {timeAgo} · failed: {lastSession.error_message || 'unknown error'}</div>;
        }
        if (lastSession.status === 'blocked') {
          return <div className="text-xs text-amber-700 mt-2 flex items-center gap-1"><span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />Last scan: {timeAgo} · blocked — source returned nothing</div>;
        }
        if (lastSession.status === 'running') {
          return <div className="text-xs text-blue-600 mt-2">Scan in progress…</div>;
        }
        return null;
      })()}

      {/* Progress bar */}
      {isScanningThis && isAnyScanRunning && (
        <div className="mt-2 h-1 w-full bg-gray-200 rounded-full overflow-hidden">
          {progress != null ? (
            <div
              className="h-full bg-emerald-500 transition-all duration-[3000ms] ease-out"
              style={{ width: `${progress}%` }}
            />
          ) : (
            <div className="h-full bg-emerald-500 animate-pulse" style={{ width: '30%' }} />
          )}
        </div>
      )}

      {/* Delete confirmation */}
      {confirmDeleteId === id && (
        <div className="mt-3 bg-red-50 border border-red-200 rounded-xl p-4 space-y-3">
          <p className="text-sm text-red-700">Delete this preset? Properties found by this preset will be kept.</p>
          <div className="flex gap-2">
            <button
              onClick={() => handleDelete(id)}
              disabled={deletePreset.isPending}
              className="flex-1 bg-red-600 text-white rounded-2xl min-h-[44px] text-sm font-semibold disabled:opacity-50"
            >
              {deletePreset.isPending ? 'Deleting…' : 'Yes, delete'}
            </button>
            <button
              onClick={() => setConfirmDeleteId(null)}
              className="flex-1 border border-gray-200 rounded-2xl min-h-[44px] text-sm text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
