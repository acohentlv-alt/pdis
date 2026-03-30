import { useNavigate } from 'react-router-dom';
import { formatPrice, formatPricePerSqm, CLASSIFICATION_STYLES } from '../lib/format';

interface PropertyCardProps {
  item: Record<string, unknown>;
}

function getSignalDetails(item: Record<string, unknown>): Record<string, unknown> {
  if (item.signal_details && typeof item.signal_details === 'object') {
    return item.signal_details as Record<string, unknown>;
  }
  return {};
}

export default function PropertyCard({ item }: PropertyCardProps) {
  const navigate = useNavigate();
  const yad2Id = item.yad2_id as string;
  const classification = (item.classification as string) ?? 'cold';
  const style = CLASSIFICATION_STYLES[classification] ?? CLASSIFICATION_STYLES.cold;
  const sd = getSignalDetails(item);

  const price = item.price as number | null;
  const sqm = item.square_meters as number | null;
  const dom = (item.days_on_market as number) ?? 0;
  const neighborhood = item.neighborhood as string | null;

  const priceDrop = (sd.price_drops as number ?? 0) > 0;
  const hasRelisting = !!(sd.has_relisting);
  const longListed = dom > 60;
  const weakLanguage = Array.isArray(sd.weak_language_found) && (sd.weak_language_found as unknown[]).length > 0;

  const imageUrls = (item.image_urls as string[] | null) ?? [];
  const isAgent = !!(item.is_agent);
  const hasParking = !!(item.parking);
  const hasElevator = !!(item.elevator);
  const hasAC = !!(item.air_conditioning);

  return (
    <div className="bg-white rounded-xl shadow overflow-hidden">
      {imageUrls.length > 0 && (
        <img
          src={imageUrls[0]}
          alt=""
          className="w-full h-40 object-cover"
          loading="lazy"
        />
      )}
      <div className="p-4 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <span dir="rtl" className="font-semibold text-gray-800 text-sm leading-snug">
          {neighborhood || 'Unknown area'}
        </span>
        <span className={`${style.bg} text-white text-xs px-2 py-0.5 rounded-full font-medium shrink-0`}>
          {style.icon} {style.label}
        </span>
      </div>

      <div className="text-sm text-gray-700">
        <span className="font-semibold">{formatPrice(price)}</span>
        {sqm && <span className="text-gray-400 ml-2">· {sqm}m²</span>}
        {price && sqm && <span className="text-gray-400 ml-2">· {formatPricePerSqm(price, sqm)}</span>}
      </div>

      {dom > 0 && (
        <div className="text-xs text-gray-500">
          {String(dom)} days on market
        </div>
      )}

      <div className="flex flex-wrap gap-1">
        {isAgent && (
          <span className="text-xs bg-purple-50 text-purple-600 px-2 py-0.5 rounded-full">Agent</span>
        )}
        {priceDrop && (
          <span className="text-xs bg-red-50 text-red-600 px-2 py-0.5 rounded-full">📉 Price drop</span>
        )}
        {hasRelisting && (
          <span className="text-xs bg-orange-50 text-orange-600 px-2 py-0.5 rounded-full">🔴 Reappeared</span>
        )}
        {longListed && (
          <span className="text-xs bg-yellow-50 text-yellow-700 px-2 py-0.5 rounded-full">⏱ Long listed</span>
        )}
        {weakLanguage && (
          <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">💬 Weak language</span>
        )}
      </div>

      {(hasParking || hasElevator || hasAC) && (
        <div className="flex gap-2 text-xs text-gray-400">
          {hasParking && <span>🅿️ Parking</span>}
          {hasElevator && <span>🛗 Elevator</span>}
          {hasAC && <span>❄️ AC</span>}
        </div>
      )}

      <div className="flex gap-2 pt-1">
        <button
          onClick={() => navigate(`/property/${yad2Id}`)}
          className="flex-1 min-h-[44px] bg-gray-900 text-white rounded-lg text-sm font-medium"
        >
          Open Card
        </button>
        {!!item.listing_url && (
          <button
            onClick={() => window.open(item.listing_url as string, '_blank')}
            className="flex-1 min-h-[44px] border border-gray-300 text-gray-700 rounded-lg text-sm font-medium"
          >
            Source →
          </button>
        )}
      </div>
      </div>
    </div>
  );
}
