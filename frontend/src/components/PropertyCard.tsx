import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { formatPrice, formatPricePerSqm } from '../lib/format';
import ImageViewer from './ImageViewer';

interface PropertyCardProps {
  item: Record<string, unknown>;
  favoriteIds?: Set<string>;
  onToggleFavorite?: (yad2Id: string, isFav: boolean) => void;
  isWhitelisted?: boolean;
  isBlacklisted?: boolean;
  onToggleWhitelist?: () => void;
  onToggleBlacklist?: () => void;
  targetPriceSqm?: number | null;
}

function getSignalDetails(item: Record<string, unknown>): Record<string, unknown> {
  if (item.signal_details && typeof item.signal_details === 'object') {
    return item.signal_details as Record<string, unknown>;
  }
  return {};
}

export default function PropertyCard({
  item,
  favoriteIds,
  onToggleFavorite,
  isWhitelisted,
  isBlacklisted,
  onToggleWhitelist,
  onToggleBlacklist,
  targetPriceSqm,
}: PropertyCardProps) {
  const navigate = useNavigate();
  const yad2Id = item.yad2_id as string;
  const sd = getSignalDetails(item);

  const price = item.price as number | null;
  const sqmBuild = item.square_meter_build as number | null;
  const sqmTotal = item.square_meters as number | null;
  const sqm = sqmBuild || sqmTotal;
  const dom = (item.days_on_market as number) ?? 0;
  const neighborhood = item.neighborhood as string | null;

  const rooms = item.rooms as number | null;
  const floor = item.floor as number | null;
  const totalFloors = item.total_floors as number | null;
  const propertyType = item.property_type as string | null;
  const hasBalcony = !!(item.balcony);

  const priceDrop = (sd.price_drops as number ?? 0) > 0;
  const hasRelisting = (sd.relisting_count as number ?? 0) > 0 || !!(sd.has_relisting);
  const longListed = dom > 60;
  const weakLanguage = Array.isArray(sd.weak_language_found) && (sd.weak_language_found as unknown[]).length > 0;
  const conditionAlert = Array.isArray(sd.condition_keywords_found) && (sd.condition_keywords_found as unknown[]).length > 0;
  const belowAvgPrice = !!(sd.below_avg_price_sqm);
  const isNew = (() => {
    const fs = item.first_seen as string | null;
    if (!fs) return false;
    const today = new Date().toISOString().slice(0, 10);
    return fs.slice(0, 10) === today;
  })();

  const imageUrls = (item.image_urls as string[] | null) ?? [];
  const isAgent = !!(item.is_agent);
  const hasParking = !!(item.parking);
  const hasElevator = !!(item.elevator);
  const hasAC = !!(item.air_conditioning);

  const source = (item.source as string) ?? 'yad2';
  const matchedSources = (item.matched_sources as string[] | null) ?? [];
  const allSources = new Set([source, ...matchedSources]);

  const sourceUrl = (item.listing_url as string) || (
    source === 'yad2' ? `https://www.yad2.co.il/item/${yad2Id}` :
    source === 'madlan' ? `https://www.madlan.co.il/listings/${yad2Id.replace('madlan_', '')}` :
    null
  );

  const isFav = favoriteIds?.has(yad2Id) ?? false;

  const [showViewer, setShowViewer] = useState(false);

  // Precomputed to avoid TS 5.9 JSX children inference issues
  let dealQualityLabel: string | null = null;
  let dealQualityColor = 'text-gray-600';
  if (targetPriceSqm != null && price != null && sqm != null) {
    const pctDiff = ((price / sqm) - targetPriceSqm) / targetPriceSqm * 100;
    dealQualityLabel = pctDiff <= 0
      ? `${Math.abs(pctDiff).toFixed(0)}% below target`
      : `${pctDiff.toFixed(0)}% above target`;
    dealQualityColor = pctDiff <= 0 ? 'text-green-600' : pctDiff <= 10 ? 'text-yellow-600' : 'text-red-500';
  }

  const whatIsItParts: string[] = [];
  if (propertyType) whatIsItParts.push(propertyType.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()));
  if (rooms != null) whatIsItParts.push(`${String(rooms)} rooms`);
  if (sqm) whatIsItParts.push(`${String(sqm)}m\u00B2${sqmBuild && sqmTotal && sqmBuild !== sqmTotal ? ` (${String(sqmTotal)} total)` : ''}`);
  const whatIsIt: string = whatIsItParts.join(' \u00B7 ');

  const priceDropTitle = `${String(sd.price_drops)}x drop, largest ${Number(sd.largest_drop_pct || 0).toFixed(1)}%${sd.last_price_drop_date ? `\nLast: ${String(sd.last_price_drop_date)}` : ''}`;

  const hasDescription = !!(item.description) && String(item.description).length > 30;
  const descriptionText = hasDescription ? String(item.description) : '';

  const hasAddress = !!(item.address_street || item.address_home_number);
  const addressText = hasAddress
    ? `, ${String(item.address_street || '')}${item.address_home_number ? ` ${String(item.address_home_number)}` : ''}`
    : '';

  return (
    <div className="bg-white rounded-xl shadow overflow-hidden">
      {imageUrls.length > 0 && (
        <img src={imageUrls[0]} alt="" className="w-full h-40 object-cover cursor-pointer" loading="lazy" onClick={() => setShowViewer(true)} />
      )}
      {showViewer && imageUrls.length > 0 && (
        <ImageViewer images={imageUrls} onClose={() => setShowViewer(false)} />
      )}
      <div className="p-4 space-y-2">
        <div className="flex items-baseline justify-between">
          <span className="text-lg font-bold text-gray-900">{formatPrice(price)}</span>
          <span className="text-lg font-bold text-blue-600">{price != null && sqm != null ? formatPricePerSqm(price, sqm) : ''}</span>
        </div>
        {dealQualityLabel && <div className={`text-xs font-medium ${dealQualityColor}`}>{dealQualityLabel}</div>}
        {whatIsIt && <div className="text-sm text-gray-600">{whatIsIt}</div>}
        <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-gray-500">
          {floor != null && <span>Floor {floor}{totalFloors != null ? `/${totalFloors}` : ''}</span>}
          <span className={hasElevator ? 'text-green-600' : 'text-red-400'}>{hasElevator ? '✓ Elevator' : '✗ No elevator'}</span>
          <span className={hasParking ? 'text-green-600' : 'text-red-400'}>{hasParking ? '✓ Parking' : '✗ No parking'}</span>
          {hasBalcony && <span>Balcony</span>}
          {hasAC && <span>A/C</span>}
        </div>
        <div dir="rtl" className="text-sm leading-snug">
          <span className="font-semibold text-gray-800">{neighborhood || 'Unknown area'}</span>
          {hasAddress && <span className="text-gray-500 mr-1">{addressText}</span>}
        </div>
        {hasDescription && (
          <div dir="rtl" className="text-xs text-gray-500 line-clamp-2 leading-relaxed">{descriptionText}</div>
        )}
        <div className="flex flex-wrap items-center gap-1">
          {dom > 0 && <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{String(dom)}d</span>}
          {isNew && <span className="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full font-medium">New</span>}
          {isAgent && <span className="text-xs bg-purple-50 text-purple-600 px-2 py-0.5 rounded-full">Agent</span>}
          {priceDrop && <span className="text-xs bg-red-50 text-red-600 px-2 py-0.5 rounded-full cursor-help" title={priceDropTitle}>Price drop</span>}
          {hasRelisting && <span className="text-xs bg-orange-50 text-orange-600 px-2 py-0.5 rounded-full">Reappeared</span>}
          {longListed && <span className="text-xs bg-yellow-50 text-yellow-700 px-2 py-0.5 rounded-full">Long listed</span>}
          {weakLanguage && <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">Weak language</span>}
          {conditionAlert && <span className="text-xs bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full">Condition</span>}
          {belowAvgPrice && <span className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded-full">Below avg</span>}
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1">
            {onToggleFavorite && (
              <button onClick={(e) => { e.stopPropagation(); onToggleFavorite(yad2Id, isFav); }} className="text-lg" title={isFav ? 'Remove from favorites' : 'Add to favorites'}>
                {isFav ? '★' : '☆'}
              </button>
            )}
            {onToggleWhitelist && (
              <button onClick={(e) => { e.stopPropagation(); onToggleWhitelist(); }}
                className={`text-sm px-1.5 py-0.5 rounded font-bold transition-colors ${isWhitelisted ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-400'}`}
                title={isWhitelisted ? 'Remove from whitelist' : 'Add to whitelist'}>✓</button>
            )}
            {onToggleBlacklist && (
              <button onClick={(e) => { e.stopPropagation(); onToggleBlacklist(); }}
                className={`text-sm px-1.5 py-0.5 rounded font-bold transition-colors ${isBlacklisted ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-400'}`}
                title={isBlacklisted ? 'Remove from blacklist' : 'Add to blacklist'}>✕</button>
            )}
          </div>
          <div className="flex items-center gap-1">
            {allSources.has('yad2') && <span className="text-xs bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded">Y2</span>}
            {allSources.has('madlan') && <span className="text-xs bg-emerald-50 text-emerald-600 px-1.5 py-0.5 rounded">MD</span>}
          </div>
        </div>
        <div className="flex gap-2 pt-1">
          <button onClick={() => navigate(`/property/${yad2Id}`)} className="flex-1 min-h-[44px] bg-gray-900 text-white rounded-lg text-sm font-medium">
            Open Card
          </button>
          {sourceUrl && (
            <button onClick={() => window.open(sourceUrl, '_blank')} className="flex-1 min-h-[44px] border border-gray-300 text-gray-700 rounded-lg text-sm font-medium">
              View on {source === 'madlan' ? 'Madlan' : 'Yad2'} →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
