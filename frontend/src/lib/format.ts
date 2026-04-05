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

export function formatDateFull(iso: string): string {
  const d = new Date(iso);
  return `${d.getDate().toString().padStart(2, '0')}.${(d.getMonth() + 1).toString().padStart(2, '0')}.${d.getFullYear()}`;
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

export const SIGNAL_LABELS: Record<string, string> = {
  price_drop_gt_10pct: "Large price drop (>10%)",
  relisted_2plus: "Relisted 2+ times",
  listed_90plus_days: "Listed 90+ days",
  weak_language: "Desperate language",
  condition_keywords: "Needs renovation",
  below_avg_price: "Below avg price/sqm",
  price_drop_small: "Price drop (small)",
  relisted_once: "Relisted once",
  listed_30_60_days: "Listed 30-60 days",
  desc_changes: "Description changed",
  img_changes: "Images changed",
};

export const CLASSIFICATION_STYLES: Record<string, { bg: string; label: string; icon: string }> = {
  hot: { bg: "bg-red-500", label: "Hot", icon: "🔥" },
  warm: { bg: "bg-orange-400", label: "Warm", icon: "⚠️" },
  cold: { bg: "bg-gray-400", label: "Cold", icon: "❌" },
};
