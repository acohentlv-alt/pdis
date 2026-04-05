export function matchesPresetCriteria(
  property: Record<string, unknown>,
  preset: Record<string, unknown>
): boolean {
  const price = property.price as number | null;
  const rooms = property.rooms as number | null;
  const propType = property.property_type as string | null;
  const sqmBuild = property.square_meter_build as number | null;
  const sqmTotal = property.square_meters as number | null;
  const sqm = sqmBuild || sqmTotal;

  if (preset.min_price != null && price != null && price < (preset.min_price as number)) return false;
  if (preset.max_price != null && price != null && price > (preset.max_price as number)) return false;
  if (preset.min_rooms != null && rooms != null && rooms < (preset.min_rooms as number)) return false;
  if (preset.max_rooms != null && rooms != null && rooms > (preset.max_rooms as number)) return false;

  const presetTypes = preset.property_types as string[] | null;
  if (presetTypes && presetTypes.length > 0 && propType) {
    if (!presetTypes.includes(propType)) return false;
  }

  // Check sqm from extra_params
  const extraParams = (preset.extra_params as Record<string, unknown>) ?? {};
  const minSqm = extraParams.min_sqm as number | null;
  const maxSqm = extraParams.max_sqm as number | null;
  if (minSqm != null && sqm != null && sqm < minSqm) return false;
  if (maxSqm != null && sqm != null && sqm > maxSqm) return false;

  return true;
}

export function computeTargetPriceSqm(preset: Record<string, unknown>): number | null {
  const maxPrice = preset.max_price as number | null;
  const extraParams = (preset.extra_params as Record<string, unknown>) ?? {};
  const minSqm = extraParams.min_sqm as number | null;
  if (maxPrice && minSqm && minSqm > 0) {
    return maxPrice / minSqm;
  }
  return null;
}
