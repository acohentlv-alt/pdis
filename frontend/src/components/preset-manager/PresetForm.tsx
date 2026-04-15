// PresetForm — dumb component, zero hooks. All state arrives via props.
import type { Dispatch, SetStateAction } from 'react';
import type {
  PresetFormData,
  PricingState,
  FaState,
} from './presetFormUtils';
import { primaryCta } from './presetFormUtils';
import { useNeighborhoods, useFbGroups } from '../../api/queries';
import {
  SectionBasics,
  SectionPriceRooms,
  SectionMoreFilters,
  SectionPricingTargets,
  SectionFeatureAdjustments,
} from './PresetFormSections';

interface PresetFormProps {
  form: PresetFormData;
  setForm: Dispatch<SetStateAction<PresetFormData>>;
  setField: (key: keyof PresetFormData, value: string | boolean) => void;
  togglePropertyType: (val: string) => void;
  formError: string | null;
  isEditing: boolean;
  titleOverride?: string;
  category?: string;
  hoodData: ReturnType<typeof useNeighborhoods>['data'];
  fbGroupsData: ReturnType<typeof useFbGroups>['data'];
  pricingTargets: PricingState;
  setPricingTargets: Dispatch<SetStateAction<PricingState>>;
  faTargets: FaState;
  setFaTargets: Dispatch<SetStateAction<FaState>>;
  pricingExpanded: boolean;
  setPricingExpanded: (v: boolean) => void;
  faExpanded: boolean;
  setFaExpanded: (v: boolean) => void;
  neighborhoodExpanded: Record<number, boolean>;
  setNeighborhoodExpanded: Dispatch<SetStateAction<Record<number, boolean>>>;
  faHoodExpanded: Record<number, boolean>;
  setFaHoodExpanded: Dispatch<SetStateAction<Record<number, boolean>>>;
  showAdvanced: boolean;
  setShowAdvanced: (v: boolean) => void;
  onSave: () => void;
  onCancel: () => void;
  saving: boolean;
}

export default function PresetForm({
  form,
  setForm,
  setField,
  togglePropertyType,
  formError,
  isEditing,
  titleOverride,
  category,
  hoodData,
  fbGroupsData,
  pricingTargets,
  setPricingTargets,
  faTargets,
  setFaTargets,
  pricingExpanded,
  setPricingExpanded,
  faExpanded,
  setFaExpanded,
  neighborhoodExpanded,
  setNeighborhoodExpanded,
  faHoodExpanded,
  setFaHoodExpanded,
  showAdvanced,
  setShowAdvanced,
  onSave,
  onCancel,
  saving,
}: PresetFormProps) {
  const title = titleOverride ?? (isEditing ? `Editing: ${form.name}` : 'New Preset');

  return (
    <>
      {/* Scrollable form body — padded at bottom so sticky footer doesn't overlap */}
      <div className="px-5 pt-4 pb-40 space-y-6">
        <div className="text-base font-bold text-gray-900">{title}</div>

        {/* Section A: Basics */}
        <SectionBasics form={form} setField={setField} category={category} />

        {/* Section B: Price & Rooms */}
        <SectionPriceRooms form={form} setField={setField} />

        {/* Section C: More filters */}
        <SectionMoreFilters
          form={form}
          setForm={setForm}
          setField={setField}
          togglePropertyType={togglePropertyType}
          showAdvanced={showAdvanced}
          setShowAdvanced={setShowAdvanced}
          hoodData={hoodData}
          fbGroupsData={fbGroupsData}
        />

        {/* Section D: Pricing Targets */}
        <SectionPricingTargets
          form={form}
          hoodData={hoodData}
          pricingTargets={pricingTargets}
          setPricingTargets={setPricingTargets}
          pricingExpanded={pricingExpanded}
          setPricingExpanded={setPricingExpanded}
          neighborhoodExpanded={neighborhoodExpanded}
          setNeighborhoodExpanded={setNeighborhoodExpanded}
        />

        {/* Section E: Feature Adjustments */}
        <SectionFeatureAdjustments
          form={form}
          hoodData={hoodData}
          faTargets={faTargets}
          setFaTargets={setFaTargets}
          faExpanded={faExpanded}
          setFaExpanded={setFaExpanded}
          faHoodExpanded={faHoodExpanded}
          setFaHoodExpanded={setFaHoodExpanded}
        />

        {/* Error banner */}
        {formError && (
          <div className="rounded-2xl bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">
            {formError}
          </div>
        )}
      </div>

      {/* Sticky footer */}
      <div className="sticky bottom-0 left-0 right-0 bg-white border-t border-gray-100 px-5 py-4 shadow-[0_-4px_12px_rgba(0,0,0,0.04)]">
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 border border-gray-200 text-gray-700 rounded-2xl py-4 min-h-[56px] font-semibold hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onSave}
            disabled={saving}
            className={`flex-1 ${primaryCta} disabled:opacity-50`}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </>
  );
}
