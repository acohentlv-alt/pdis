export function formatPrice(price: number | null): string {
  if (price == null) return "N/A";
  return price.toLocaleString("he-IL") + " ₪";
}

export function formatPricePerSqm(price: number | null, sqm: number | null): string {
  if (!price || !sqm || sqm === 0) return "N/A";
  return Math.round(price / sqm).toLocaleString("he-IL") + " ₪/m²";
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  return `${d.getDate().toString().padStart(2, '0')}.${(d.getMonth() + 1).toString().padStart(2, '0')}`;
}

export const EVENT_LABELS: Record<string, string> = {
  new_listing: "First listed",
  price_drop: "Price drop",
  price_increase: "Price increase",
  removal: "Removed",
  relisting: "Relisted",
  description_change: "Description changed",
  image_change: "Images changed",
};

export const CLASSIFICATION_STYLES: Record<string, { bg: string; label: string; icon: string }> = {
  hot: { bg: "bg-red-500", label: "Hot", icon: "🔥" },
  warm: { bg: "bg-orange-400", label: "Warm", icon: "⚠️" },
  cold: { bg: "bg-gray-400", label: "Cold", icon: "❌" },
};
