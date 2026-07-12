import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { formatPrice, formatPricePerSqm, formatUpdatedAgo } from '../lib/format';
import { sourceUrl as buildSourceUrl } from '../lib/sourceUrl';
import { logEvent } from '../lib/telemetry';
import ImageViewer from './ImageViewer';

interface PropertyCardProps {
  item: Record<string, unknown>;
  favoriteIds?: Set<string>;
  onToggleFavorite?: (yad2Id: string, isFav: boolean) => void;
  isWhitelisted?: boolean;
  isBlacklisted?: boolean;
  onToggleWhitelist?: () => void;
  onToggleBlacklist?: () => void;
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
}: PropertyCardProps) {
  const navigate = useNavigate();
  const yad2Id = item.yad2_id as string;
  const sd = getSignalDetails(item);

  const price = item.price as number | null;
  const sqm = item.display_sqm as number | null;
  const dom = (item.days_on_market as number) ?? 0;
  const neighborhood = item.neighborhood as string | null;
  const updatedAgo = formatUpdatedAgo(item.last_seen as string | null | undefined);

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

  const sourceUrl = buildSourceUrl(item.listing_url as string | null, source, yad2Id);

  const isFav = favoriteIds?.has(yad2Id) ?? false;

  const [showViewer, setShowViewer] = useState(false);
  const [phoneRevealed, setPhoneRevealed] = useState(false);

  const formatPhone = (raw: string): string => {
    const digits = raw.replace(/\D/g, '');
    if (digits.length === 10 && digits.startsWith('0')) {
      return `${digits.slice(0, 3)}-${digits.slice(3, 6)}-${digits.slice(6)}`;
    }
    if (digits.length === 9 && digits.startsWith('0')) {
      return `${digits.slice(0, 2)}-${digits.slice(2, 5)}-${digits.slice(5)}`;
    }
    return raw;
  };

  const whatIsItParts: string[] = [];
  if (propertyType) whatIsItParts.push(propertyType.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()));
  if (rooms != null) whatIsItParts.push(`${String(rooms)} rooms`);
  if (sqm) whatIsItParts.push(`${String(sqm)}m\u00B2`);
  const whatIsIt: string = whatIsItParts.join(' \u00B7 ');

  const priceDropTitle = `${String(sd.price_drops)}x drop, largest ${Number(sd.largest_drop_pct || 0).toFixed(1)}%${sd.last_price_drop_date ? `\nLast: ${String(sd.last_price_drop_date)}` : ''}`;

  const hasDescription = !!(item.description) && String(item.description).length > 30;
  const descriptionText = hasDescription ? String(item.description) : '';

  const hasAddress = !!(item.address_street || item.address_home_number);

  const signalDetails = sd as Record<string, unknown> & {
    buyer_fit_tags?: string[];
    amit_pct_vs_preferred?: number | null;
    strong_signals?: string[];
    weak_signals?: string[];
  };

  const hasAmitPill =
    signalDetails?.buyer_fit_tags?.includes('below_amit_target') ||
    signalDetails?.buyer_fit_tags?.includes('close_to_amit_target');
  const addressText = hasAddress
    ? `, ${String(item.address_street || '')}${item.address_home_number ? ` ${String(item.address_home_number)}` : ''}`
    : '';

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 hover:border-gray-200 hover:shadow-md transition-all overflow-hidden">
      {signalDetails?.buyer_fit_tags?.includes('below_amit_target') &&
       (signalDetails?.strong_signals?.length ?? 0) > 0 && (
        <div className="bg-amber-400 text-amber-950 font-bold text-xs uppercase tracking-wider py-1.5 text-center">
          🎯 PRIME DEAL
        </div>
      )}
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
          {updatedAgo && (
            <span className={`text-xs px-2 py-0.5 rounded-full ${updatedAgo.isToday ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
              {updatedAgo.label}
            </span>
          )}
          {isNew && <span className="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full font-medium">New</span>}
          {isAgent && <span className="text-xs bg-purple-50 text-purple-600 px-2 py-0.5 rounded-full">Agent</span>}
          {priceDrop && <span className="text-xs bg-red-50 text-red-600 px-2 py-0.5 rounded-full cursor-help" title={priceDropTitle}>Price drop</span>}
          {hasRelisting && <span className="text-xs bg-orange-50 text-orange-600 px-2 py-0.5 rounded-full">Reappeared</span>}
          {longListed && <span className="text-xs bg-yellow-50 text-yellow-700 px-2 py-0.5 rounded-full">Long listed</span>}
          {weakLanguage && <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">Weak language</span>}
          {conditionAlert && <span className="text-xs bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full">Condition</span>}
          {signalDetails?.buyer_fit_tags?.includes('below_amit_target') && signalDetails?.amit_pct_vs_preferred != null && (
            <span className="inline-flex items-center rounded-full bg-green-100 text-green-800 px-2 py-0.5 text-xs font-medium">
              Amit Fit · −{Math.abs(Math.round(signalDetails.amit_pct_vs_preferred as number))}%
            </span>
          )}
          {signalDetails?.buyer_fit_tags?.includes('close_to_amit_target') && signalDetails?.amit_pct_vs_preferred != null && (
            <span className="inline-flex items-center rounded-full bg-yellow-100 text-yellow-800 px-2 py-0.5 text-xs font-medium">
              Close · +{Math.abs(Math.round(signalDetails.amit_pct_vs_preferred as number))}%
            </span>
          )}
          {!hasAmitPill && belowAvgPrice && <span className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded-full">Below avg</span>}
        </div>
        {(item.contact_phone as string | null) ? (
          phoneRevealed ? (
            <a
              href={`tel:${item.contact_phone as string}`}
              onClick={(e) => e.stopPropagation()}
              className="inline-flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white font-semibold text-sm px-4 py-2.5 rounded-xl shadow-sm shadow-emerald-600/20 transition-colors no-underline w-full justify-center"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
              </svg>
              <span className="tabular-nums">{formatPhone(item.contact_phone as string)}</span>
            </a>
          ) : (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setPhoneRevealed(true);
                logEvent(
                  'phone_reveal',
                  { source: item?.source, price: item?.price },
                  { yad2_id: yad2Id }
                );
              }}
              aria-label="Reveal phone number"
              title="Tap to reveal phone"
              className="inline-flex items-center gap-2 bg-gray-50 hover:bg-gray-100 border border-gray-200 hover:border-gray-300 text-gray-700 font-medium text-sm px-4 py-2.5 rounded-xl transition-colors w-full justify-center"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
              </svg>
              <span className="tabular-nums">{(item.contact_phone as string).replace(/\D/g, '').slice(0, 3)}-•••-••••</span>
              <span className="text-xs text-gray-500 ml-1">Tap to call</span>
            </button>
          )
        ) : source === 'facebook' && sourceUrl ? (
          <div className="flex items-center gap-2 text-sm">
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 underline"
              onClick={(e) => e.stopPropagation()}
            >
              Message on Facebook →
            </a>
          </div>
        ) : null}
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
            {allSources.has('facebook') && <span className="text-xs bg-indigo-50 text-indigo-600 px-1.5 py-0.5 rounded">FB</span>}
          </div>
        </div>
        <div className="flex gap-2 pt-1">
          <button onClick={() => navigate(`/property/${yad2Id}`)} className="flex-1 min-h-[44px] bg-gray-900 text-white rounded-lg text-sm font-medium">
            Open Card
          </button>
          {sourceUrl && (
            <button onClick={() => window.open(sourceUrl, '_blank')} className="flex-1 min-h-[44px] border border-gray-300 text-gray-700 rounded-lg text-sm font-medium">
              View on {source === 'madlan' ? 'Madlan' : source === 'facebook' ? 'Facebook' : 'Yad2'} →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
