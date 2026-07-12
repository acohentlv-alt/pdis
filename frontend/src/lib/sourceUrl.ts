/**
 * Builds the outbound "view on source" URL for a property.
 * Prefers the stored listing_url; falls back to constructing one from the
 * yad2_id for sources where we know the URL pattern (yad2, madlan).
 * Facebook has no reliable URL-from-id construction — listing_url or null.
 */
export function sourceUrl(
  listingUrl: string | null | undefined,
  source: string | null | undefined,
  yad2Id: string | null | undefined
): string | null {
  if (listingUrl) return listingUrl;
  const id = yad2Id ?? '';
  if (source === 'yad2') return `https://www.yad2.co.il/item/${id}`;
  if (source === 'madlan') return `https://www.madlan.co.il/listings/${id.replace('madlan_', '')}`;
  return null;
}
