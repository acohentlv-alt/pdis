import { useState, useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  useAllPresets,
  useNeighborhoods,
  useThresholds,
  useFeatureAdjustments,
  useFbGroups,
  useScanStatus,
} from '../../api/queries';
import {
  useCreatePreset,
  useUpdatePreset,
  useDeletePreset,
  useToggleScanEnabled,
  useToggleVisibility,
  useClonePreset,
  useScanPreset,
  useTriggerYad2Manual,
  useUpsertThresholds,
  useUpsertFeatureAdjustments,
} from '../../api/mutations';
import {
  emptyForm,
  validate,
  formToPayload,
  presetToForm,
  hasAdvancedFilters,
  type PresetFormData,
  type PricingState,
  type FaState,
  SIZE_BUCKETS,
  bucketKey,
  _DEFAULT_FA,
} from './presetFormUtils';
import PresetRow from './PresetRow';
import PresetFormComponent from './PresetForm';

interface PresetManagerProps {
  open: boolean;
  onClose: () => void;
  category?: string;
}

export default function PresetManager({ open, onClose, category }: PresetManagerProps) {
  // ── ALL HOOKS — must be before any conditional return ──────────────────────

  const queryClient = useQueryClient();
  const [showHidden, setShowHidden] = useState(false);
  const { data, isLoading } = useAllPresets(showHidden);
  const createPreset = useCreatePreset();
  const updatePreset = useUpdatePreset();
  const deletePreset = useDeletePreset();
  const toggleScanEnabled = useToggleScanEnabled();
  const toggleVisibility = useToggleVisibility();
  const clonePreset = useClonePreset();
  const scanPreset = useScanPreset();
  const triggerYad2 = useTriggerYad2Manual();
  const { data: scanStatus } = useScanStatus();
  const { data: fbGroupsData } = useFbGroups();

  const [activeScanPresetId, setActiveScanPresetId] = useState<number | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const [yad2TriggerError, setYad2TriggerError] = useState<string | null>(null);

  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<PresetFormData>(emptyForm());
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // openKebabId: 22nd hook — still before early return
  const [openKebabId, setOpenKebabId] = useState<number | null>(null);

  // Must be before early return — hooks cannot be conditional
  const { data: hoodData } = useNeighborhoods(form.city_code || null);

  const upsertThresholds = useUpsertThresholds();

  const [pricingTargets, setPricingTargets] = useState<PricingState>({});
  const [pricingExpanded, setPricingExpanded] = useState(false);
  const [neighborhoodExpanded, setNeighborhoodExpanded] = useState<Record<number, boolean>>({});

  const hasAmitSections = form.category === 'forsale';
  const { data: thresholdsData } = useThresholds('forsale', open && hasAmitSections);

  const seededKeyRef = useRef<string | null>(null);

  const upsertFeatureAdjustments = useUpsertFeatureAdjustments();
  const { data: faData } = useFeatureAdjustments('forsale', open && hasAmitSections);

  const [faTargets, setFaTargets] = useState<FaState>({});
  const [faExpanded, setFaExpanded] = useState(false);
  const [faHoodExpanded, setFaHoodExpanded] = useState<Record<number, boolean>>({});
  const seededFaKeyRef = useRef<string | null>(null);
  const prevRunningRef = useRef(false);

  // Detect when a scan finishes and refresh preset stats
  useEffect(() => {
    const running = scanStatus?.running ?? false;
    if (prevRunningRef.current && !running && activeScanPresetId !== null) {
      queryClient.invalidateQueries({ queryKey: ['presetStats'] });
      queryClient.invalidateQueries({ queryKey: ['presetLastSession', activeScanPresetId] });
      setActiveScanPresetId(null);
    }
    prevRunningRef.current = running;
  }, [scanStatus?.running, activeScanPresetId, queryClient]);

  // Seed FA targets from DB
  useEffect(() => {
    const currentKey = `${editingId ?? 'none'}-${showCreate ? 'create' : 'noedit'}`;
    if (!faData?.adjustments || !hoodData?.neighborhoods) return;
    if (seededFaKeyRef.current === currentKey) return;
    seededFaKeyRef.current = currentKey;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const hoodNameToId = new Map(hoodData.neighborhoods.map((h: any) => [h.neighborhood, h.hood_id]));
    const seeded: FaState = {};
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    for (const a of faData.adjustments as any[]) {
      const hoodId = a.hood_id ?? hoodNameToId.get(a.neighborhood);
      if (hoodId == null) continue;
      seeded[hoodId] = {
        year_old_pref: String(a.year_old_pref_pct),
        year_old_max: String(a.year_old_max_pct),
        year_mid_old_pref: String(a.year_mid_old_pref_pct),
        year_mid_old_max: String(a.year_mid_old_max_pct),
        year_mid_pref: String(a.year_mid_pref_pct),
        year_mid_max: String(a.year_mid_max_pct),
        year_new_pref: String(a.year_new_pref_pct),
        year_new_max: String(a.year_new_max_pct),
        walkup: String(a.walkup_pct_per_floor),
        parking_pref: String(a.parking_bonus_pref),
        parking_max: String(a.parking_bonus_max),
        mamad_pref: String(a.mamad_pct_pref),
        mamad_max: String(a.mamad_pct_max),
      };
    }
    setFaTargets(seeded);
  }, [faData, hoodData, editingId, showCreate]);

  // Seed pricing targets from DB
  useEffect(() => {
    const currentKey = `${editingId ?? 'none'}-${showCreate ? 'create' : 'noedit'}`;
    if (!thresholdsData?.thresholds || !hoodData?.neighborhoods) return;
    if (seededKeyRef.current === currentKey) return;
    seededKeyRef.current = currentKey;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const hoodNameToId = new Map(hoodData.neighborhoods.map((h: any) => [h.neighborhood, h.hood_id]));
    const seeded: PricingState = {};
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    for (const t of thresholdsData.thresholds as any[]) {
      const hoodId = t.hood_id ?? hoodNameToId.get(t.neighborhood);
      if (hoodId == null) continue;
      if (!seeded[hoodId]) seeded[hoodId] = {};
      seeded[hoodId][bucketKey(t.size_min, t.size_max)] = {
        pref: String(t.target_price_per_sqm_preferred),
        max: String(t.target_price_per_sqm_max),
      };
    }
    setPricingTargets(seeded);
  }, [thresholdsData, hoodData, editingId, showCreate]);

  // Reset seeded refs when closed
  useEffect(() => {
    if (!open) {
      seededKeyRef.current = null;
      seededFaKeyRef.current = null;
    }
  }, [open]);

  // Reset showHidden to default when modal closes
  useEffect(() => {
    if (!open) {
      setShowHidden(false);
    }
  }, [open]);

  // ── EARLY RETURN ───────────────────────────────────────────────────────────
  if (!open) return null;

  // ── DERIVED + HANDLERS ────────────────────────────────────────────────────

  const allPresets = (data?.presets ?? []) as Record<string, unknown>[];
  const activePresets = allPresets.filter(p => (p.is_visible as boolean) ?? true);
  const hiddenPresets = allPresets.filter(p => !(p.is_visible as boolean));
  const presets = showHidden ? allPresets : activePresets;
  const isFormOpen = showCreate || editingId !== null;
  const saving = createPreset.isPending || updatePreset.isPending || upsertThresholds.isPending || upsertFeatureAdjustments.isPending;

  function startCreate() {
    setForm({ ...emptyForm(), category: 'rent' });
    setFormError(null);
    setEditingId(null);
    setShowCreate(true);
    setShowAdvanced(false);
  }

  function startEdit(preset: Record<string, unknown>) {
    const f = presetToForm(preset);
    setForm(f);
    setFormError(null);
    setEditingId(preset.id as number);
    setShowCreate(false);
    // Auto-open advanced section if any advanced field is set (Issue 5)
    setShowAdvanced(hasAdvancedFilters(f));
  }

  function cancelForm() {
    setShowCreate(false);
    setEditingId(null);
    setFormError(null);
    setShowAdvanced(false);
    setPricingTargets({});
    setNeighborhoodExpanded({});
    setPricingExpanded(false);
    seededKeyRef.current = null;
    setFaTargets({});
    setFaHoodExpanded({});
    setFaExpanded(false);
    seededFaKeyRef.current = null;
  }

  function handleOuterClose() {
    setPricingTargets({});
    setNeighborhoodExpanded({});
    setPricingExpanded(false);
    seededKeyRef.current = null;
    setFaTargets({});
    setFaHoodExpanded({});
    setFaExpanded(false);
    seededFaKeyRef.current = null;
    onClose();
  }

  async function handleSubmit() {
    const error = validate(form);
    if (error) { setFormError(error); return; }
    setFormError(null);

    type ThresholdRow = {
      neighborhood: string; hood_id: number; category: string;
      size_min: number; size_max: number;
      target_price_per_sqm_preferred: number; target_price_per_sqm_max: number;
    };
    const thresholdsToSave: ThresholdRow[] = [];
    if (form.category === 'forsale' && hoodData?.neighborhoods) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const hoodIdToName = new Map(hoodData.neighborhoods.map((h: any) => [h.hood_id, h.neighborhood]));
      const selectedHoods = form.neighborhood?.split(',').filter(Boolean).map(Number) || [];
      for (const hoodId of selectedHoods) {
        const name = hoodIdToName.get(hoodId);
        if (!name) continue;
        const buckets = pricingTargets[hoodId] || {};
        for (const [lo, hi] of SIZE_BUCKETS) {
          const row = buckets[bucketKey(lo, hi)];
          if (!row) continue;
          const prefStr = row.pref.trim();
          const maxStr = row.max.trim();
          if (!prefStr && !maxStr) continue;
          if (!prefStr || !maxStr) {
            setFormError(`${name} ${lo}-${hi} sqm: please fill both Preferred and Max (or clear both).`);
            return;
          }
          const pref = parseInt(prefStr, 10);
          const mx = parseInt(maxStr, 10);
          if (!Number.isInteger(pref) || !Number.isInteger(mx) || pref <= 0 || mx < pref) {
            setFormError(`${name} ${lo}-${hi} sqm: Max must be at least Preferred, both greater than 0.`);
            return;
          }
          thresholdsToSave.push({
            neighborhood: name, hood_id: hoodId, category: 'forsale',
            size_min: lo, size_max: hi,
            target_price_per_sqm_preferred: pref, target_price_per_sqm_max: mx,
          });
        }
      }
    }

    type FaRowSave = {
      neighborhood: string; hood_id: number; category: string;
      year_old_pref_pct: number; year_old_max_pct: number;
      year_mid_old_pref_pct: number; year_mid_old_max_pct: number;
      year_mid_pref_pct: number; year_mid_max_pct: number;
      year_new_pref_pct: number; year_new_max_pct: number;
      walkup_pct_per_floor: number;
      parking_bonus_pref: number; parking_bonus_max: number;
      mamad_pct_pref: number; mamad_pct_max: number;
    };
    const faToSave: FaRowSave[] = [];
    if (form.category === 'forsale' && hoodData?.neighborhoods) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const hoodIdToName = new Map(hoodData.neighborhoods.map((h: any) => [h.hood_id, h.neighborhood]));
      const selectedHoods = form.neighborhood?.split(',').filter(Boolean).map(Number) || [];
      for (const hoodId of selectedHoods) {
        const name = hoodIdToName.get(hoodId);
        if (!name) continue;
        const r = faTargets[hoodId];
        if (!r) continue;

        const n = (s: string) => (s.trim() === '' ? NaN : Number(s));
        const yOp = n(r.year_old_pref), yOm = n(r.year_old_max);
        const yMOp = n(r.year_mid_old_pref), yMOm = n(r.year_mid_old_max);
        const yMp = n(r.year_mid_pref), yMm = n(r.year_mid_max);
        const yNp = n(r.year_new_pref), yNm = n(r.year_new_max);
        const w = n(r.walkup);
        const pP = n(r.parking_pref), pM = n(r.parking_max);
        const mP = n(r.mamad_pref), mM = n(r.mamad_max);
        const allNums = [yOp, yOm, yMOp, yMOm, yMp, yMm, yNp, yNm, w, pP, pM, mP, mM];
        if (allNums.some(v => !Number.isFinite(v))) {
          setFormError(`${name}: all Feature Adjustments fields are required.`);
          return;
        }
        if (w < 0 || w > 10) {
          setFormError(`${name}: Walk-up % per floor must be between 0 and 10.`);
          return;
        }
        if (yOm < yOp) { setFormError(`${name} year (old): Max must be >= Preferred.`); return; }
        if (yMOm < yMOp) { setFormError(`${name} year (mid-old): Max must be >= Preferred.`); return; }
        if (yMm < yMp) { setFormError(`${name} year (mid): Max must be >= Preferred.`); return; }
        if (yNm < yNp) { setFormError(`${name} year (new): Max must be >= Preferred.`); return; }
        if (pM < pP) { setFormError(`${name} parking: Max must be >= Preferred.`); return; }
        if (mM < mP) { setFormError(`${name} mamad: Max must be >= Preferred.`); return; }

        faToSave.push({
          neighborhood: name, hood_id: hoodId, category: 'forsale',
          year_old_pref_pct: yOp, year_old_max_pct: yOm,
          year_mid_old_pref_pct: yMOp, year_mid_old_max_pct: yMOm,
          year_mid_pref_pct: yMp, year_mid_max_pct: yMm,
          year_new_pref_pct: yNp, year_new_max_pct: yNm,
          walkup_pct_per_floor: w,
          parking_bonus_pref: pP, parking_bonus_max: pM,
          mamad_pct_pref: mP, mamad_pct_max: mM,
        });
      }
    }

    const wasCreate = editingId === null;
    try {
      if (!wasCreate) {
        await updatePreset.mutateAsync({ id: editingId as number, ...formToPayload(form) });
      } else {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const created = await createPreset.mutateAsync(formToPayload(form));
        if (created && typeof (created as any).id === 'number') {
          setEditingId((created as any).id);
        }
      }
      if (thresholdsToSave.length > 0) {
        await upsertThresholds.mutateAsync(thresholdsToSave);
      }
      if (faToSave.length > 0) {
        await upsertFeatureAdjustments.mutateAsync(faToSave);
      }
      if (wasCreate) setShowCreate(false);
      setEditingId(null);
      setPricingTargets({});
      setNeighborhoodExpanded({});
      setPricingExpanded(false);
      seededKeyRef.current = null;
      setFaTargets({});
      setFaHoodExpanded({});
      setFaExpanded(false);
      seededFaKeyRef.current = null;
    } catch (e: unknown) {
      setFormError(`Save failed: ${e instanceof Error ? e.message : 'unknown error'}`);
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

  // ── RENDER ─────────────────────────────────────────────────────────────────

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[55] animate-fade-in"
        onClick={() => {
          cancelForm();
          handleOuterClose();
        }}
      />

      {/* Bottom sheet */}
      <div
        className="fixed left-0 right-0 bg-white rounded-t-3xl z-[60] max-h-[88vh] overflow-y-auto shadow-2xl animate-slide-up"
        style={{ bottom: 'calc(4rem + env(safe-area-inset-bottom))' }}
      >
        {/* Drag handle */}
        <div className="sticky top-0 bg-white pt-3 pb-1 z-10">
          <div className="mx-auto w-10 h-1 bg-gray-300 rounded-full" />
        </div>

        {/* Sticky header */}
        <div className="sticky top-4 bg-white px-5 pt-2 pb-3 flex items-center justify-between z-10 border-b border-gray-100">
          <span className="text-xl font-bold text-gray-900 tracking-tight">Manage Presets</span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setYad2TriggerError(null);
                triggerYad2.mutate(undefined, {
                  onError: (e: unknown) => setYad2TriggerError(e instanceof Error ? e.message : 'Failed to trigger Yad2 run'),
                });
              }}
              disabled={triggerYad2.isPending || (scanStatus?.running ?? false)}
              className="text-sm font-medium px-3 py-1.5 rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors min-h-[36px]"
              title={yad2TriggerError ?? undefined}
            >
              {(triggerYad2.isPending || (scanStatus?.running ?? false))
                ? `Running\u2026 ${scanStatus?.progress != null ? `${scanStatus.progress}%` : ''}`
                : yad2TriggerError
                  ? 'Run Yad2 now \u26a0\ufe0f'
                  : 'Run Yad2 now'}
            </button>
            <button
              onClick={() => { cancelForm(); handleOuterClose(); }}
              className="text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-full text-lg min-h-[44px] min-w-[44px] flex items-center justify-center transition-colors"
              aria-label="Close"
            >
              &#x2715;
            </button>
          </div>
        </div>

        {/* Form view — shown when create or editing */}
        {isFormOpen ? (
          <PresetFormComponent
            form={form}
            setForm={setForm}
            setField={setField}
            togglePropertyType={togglePropertyType}
            formError={formError}
            isEditing={editingId !== null}
            category={category}
            hoodData={hoodData}
            fbGroupsData={fbGroupsData}
            pricingTargets={pricingTargets}
            setPricingTargets={setPricingTargets}
            faTargets={faTargets}
            setFaTargets={setFaTargets}
            pricingExpanded={pricingExpanded}
            setPricingExpanded={setPricingExpanded}
            faExpanded={faExpanded}
            setFaExpanded={setFaExpanded}
            neighborhoodExpanded={neighborhoodExpanded}
            setNeighborhoodExpanded={setNeighborhoodExpanded}
            faHoodExpanded={faHoodExpanded}
            setFaHoodExpanded={setFaHoodExpanded}
            showAdvanced={showAdvanced}
            setShowAdvanced={setShowAdvanced}
            onSave={handleSubmit}
            onCancel={cancelForm}
            saving={saving}
          />
        ) : (
          /* List view */
          <div className="px-5 pt-4 pb-8 space-y-3">
            {/* Toggle + count row */}
            <div className="flex items-center justify-between px-1 pb-1">
              <span className="text-xs text-gray-500">
                {showHidden
                  ? `${activePresets.length} active · ${hiddenPresets.length} hidden`
                  : `${activePresets.length} active`}
              </span>
              <button
                onClick={() => setShowHidden(v => !v)}
                className="flex items-center gap-2 text-xs text-gray-600 hover:text-gray-900 min-h-[44px] px-2 rounded-lg hover:bg-gray-50 transition-colors"
                aria-pressed={showHidden}
              >
                <span className={`w-8 h-4 rounded-full transition-colors flex items-center px-0.5 ${showHidden ? 'bg-gray-900' : 'bg-gray-300'}`}>
                  <span className={`block w-3 h-3 bg-white rounded-full shadow transition-transform ${showHidden ? 'translate-x-4' : 'translate-x-0'}`} />
                </span>
                <span>Show hidden</span>
              </button>
            </div>

            {/* Add Preset button — at TOP of list */}
            <button
              onClick={startCreate}
              className="w-full border-2 border-dashed border-gray-300 rounded-2xl py-4 min-h-[56px] text-gray-500 hover:border-gray-900 hover:text-gray-900 font-semibold transition-colors text-sm"
            >
              + Add Preset
            </button>

            {isLoading && (
              <div className="text-center text-gray-400 py-8">Loading…</div>
            )}

            {!isLoading && presets.length === 0 && (
              <div className="text-center text-gray-400 py-8">
                {showHidden ? 'No presets yet.' : 'No active presets.'}
              </div>
            )}

            {/* Scan error banner */}
            {scanError && (
              <div className="rounded-2xl bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm flex items-start gap-2">
                <span className="flex-1">{scanError}</span>
                <button onClick={() => setScanError(null)} className="text-red-600 underline text-xs shrink-0">dismiss</button>
              </div>
            )}

            {/* Preset list */}
            {presets.map(preset => (
              <PresetRow
                key={preset.id as number}
                preset={preset}
                editingId={editingId}
                activeScanPresetId={activeScanPresetId}
                setActiveScanPresetId={setActiveScanPresetId}
                scanStatus={scanStatus}
                scanPreset={scanPreset}
                startEdit={startEdit}
                clonePreset={clonePreset}
                toggleScanEnabled={toggleScanEnabled}
                toggleVisibility={toggleVisibility}
                confirmDeleteId={confirmDeleteId}
                setConfirmDeleteId={setConfirmDeleteId}
                deletePreset={deletePreset}
                handleDelete={handleDelete}
                setScanError={setScanError}
                hoodData={hoodData}
                openKebabId={openKebabId}
                setOpenKebabId={setOpenKebabId}
              />
            ))}

            {/* Second empty-state: toggle ON but no hidden presets exist */}
            {showHidden && hiddenPresets.length === 0 && activePresets.length > 0 && (
              <div className="text-center text-gray-400 text-xs py-2">
                No hidden presets.
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}
