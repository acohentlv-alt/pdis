import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useProperty, useSignals, useEvents, useOperatorInput, useMatches } from '../api/queries';
import { useWhitelist, useRemoveWhitelist, useBlacklist, useRemoveBlacklist, useAddFavorite, useRemoveFavorite } from '../api/mutations';
import { formatPrice, formatPricePerSqm, formatDate, formatDateFull, CLASSIFICATION_STYLES } from '../lib/format';
import LifecycleTimeline from '../components/LifecycleTimeline';
import ImageViewer from '../components/ImageViewer';
import OperatorInputForm from '../components/OperatorInputForm';
import NotesList from '../components/NotesList';

const SIGNAL_LABELS: Record<string, string> = {
  price_drop_gt_10pct: "Large price drop (>10%)",
  relisted_2plus: "Relisted 2+ times",
  listed_90plus_days: "Listed 90+ days",
  weak_language: "Desperate language detected",
  condition_keywords: "Needs renovation",
  below_avg_price: "Below neighborhood average price/sqm",
  price_drop_small: "Price drop (≤10%)",
  relisted_once: "Relisted once",
  listed_30_60_days: "Listed 30-60 days",
  desc_changes: "Description changed",
  img_changes: "Images changed",
  move_in_urgent: "Urgent move-in date",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl shadow p-4 space-y-3">
      <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">{title}</h2>
      {children}
    </div>
  );
}

interface SignalRowProps {
  label: string;
  active: boolean;
  extra?: string;
}

function SignalRow({ label, active, extra }: SignalRowProps) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className={active ? 'text-green-500' : 'text-gray-300'}>{active ? '✓' : '✗'}</span>
      <span className={active ? 'text-gray-800' : 'text-gray-400'}>{label}</span>
      {extra && <span className="text-gray-400 text-xs ml-auto">{extra}</span>}
    </div>
  );
}

function highlightKeywords(text: string, keywords: string[]): React.ReactNode {
  if (!keywords.length) return text;
  const escaped = keywords.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const regex = new RegExp(`(${escaped.join('|')})`, 'g');
  const parts = text.split(regex);
  return parts.map((part, i) =>
    keywords.includes(part)
      ? <mark key={i} className="bg-yellow-200 px-0.5 rounded">{part}</mark>
      : <span key={i}>{part}</span>
  );
}

export default function PropertyDetailPage() {
  const { yad2Id } = useParams<{ yad2Id: string }>();
  const navigate = useNavigate();

  const { data: prop, isLoading } = useProperty(yad2Id);
  useSignals(yad2Id);
  const { data: eventsData } = useEvents(yad2Id);
  useOperatorInput(yad2Id);
  const { data: matchesData } = useMatches(yad2Id);

  const whitelist = useWhitelist();
  const removeWhitelist = useRemoveWhitelist();
  const blacklist = useBlacklist();
  const removeBlacklist = useRemoveBlacklist();
  const addFav = useAddFavorite();
  const removeFav = useRemoveFavorite();
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerStartIndex, setViewerStartIndex] = useState(0);

  if (isLoading || !prop) {
    return (
      <div className="max-w-lg mx-auto px-4 py-8 text-center text-gray-400">
        Loading…
      </div>
    );
  }

  const classification = (prop.classification as Record<string, unknown> | null);
  const cls = (classification?.classification as string) ?? 'cold';
  const sd = (classification?.signal_details as Record<string, unknown>) ?? {};
  const style = CLASSIFICATION_STYLES[cls] ?? CLASSIFICATION_STYLES.cold;

  const price = prop.price as number | null;
  const sqm = prop.square_meters as number | null;
  const dom = (prop.days_on_market as number) ?? 0;

  // Signal details — support both new tier-based and old shapes
  const strongSignals = (sd.strong_signals as string[]) ?? [];
  const weakSignals = (sd.weak_signals as string[]) ?? [];
  const hasTierSignals = strongSignals.length > 0 || weakSignals.length > 0;

  // Old shape fields (still used for summary + description highlighting)
  const priceDrops = (sd.price_drops as number) ?? 0;
  const hasRelisting = hasTierSignals
    ? (sd.relisting_count as number ?? 0) > 0
    : !!(sd.has_relisting);
  const descChanges = (sd.desc_changes as number) ?? 0;
  const imgChanges = (sd.img_changes as number) ?? 0;
  const weakLanguage = Array.isArray(sd.weak_language_found) ? sd.weak_language_found as unknown[] : [];
  const conditionKeywords = Array.isArray(sd.condition_keywords_found) ? sd.condition_keywords_found as string[] : [];

  // Summary line
  const summaryParts: string[] = [];
  if (hasRelisting) summaryParts.push('Returned after removal');
  if (priceDrops > 0) summaryParts.push('Price drop');
  if (conditionKeywords.length > 0) summaryParts.push('Condition note');
  if (dom > 60) summaryParts.push('Long on market');
  if (weakLanguage.length > 0) summaryParts.push('Weak language');

  // Property evolution
  const snapshots = (prop.snapshots as Record<string, unknown>[]) ?? [];
  const firstPrice = snapshots.length > 0
    ? (snapshots[snapshots.length - 1].price as number | null)
    : null;
  const priceChange = (firstPrice && price && firstPrice !== 0)
    ? Math.round(((price - firstPrice) / firstPrice) * 100)
    : null;

  const events = (eventsData?.events as Record<string, unknown>[]) ?? [];
  const relistingCount = events.filter(e => e.event_type === 'relisting').length;
  const attempts = relistingCount + 1;

  const notes = (prop.notes as { id: number; note: string; created_by: string; created_at: string }[]) ?? [];
  const matches = (matchesData?.matches as Record<string, unknown>[]) ?? [];
  const isWhitelisted = !!(prop.is_whitelisted);
  const isBlacklisted = !!(prop.is_blacklisted);
  const isFavorited = !!(prop.is_favorited);

  const imageUrls = (prop.image_urls as string[] | null) ?? [];
  const yad2DateAdded = prop.yad2_date_added as string | null;

  const isAgent = !!(prop.is_agent);
  const agentOffice = prop.agent_office as string | null;
  const moveInDate = prop.move_in_date as string | null;
  const source = (prop.source as string) ?? 'yad2';

  const amenities = [
    { key: 'parking', label: 'Parking', active: !!(prop.parking) },
    { key: 'elevator', label: 'Elevator', active: !!(prop.elevator) },
    { key: 'safe_room', label: 'Safe room', active: !!(prop.safe_room) },
    { key: 'renovated', label: 'Renovated', active: !!(prop.renovated) },
    { key: 'balcony', label: 'Balcony', active: !!(prop.balcony) },
    { key: 'pets_allowed', label: 'Pets', active: !!(prop.pets_allowed) },
    { key: 'furnished', label: 'Furnished', active: !!(prop.furnished) },
    { key: 'air_conditioning', label: 'AC', active: !!(prop.air_conditioning) },
    { key: 'accessibility', label: 'Accessible', active: !!(prop.accessibility) },
  ];

  return (
    <div className="max-w-lg mx-auto px-4 py-4 space-y-4">
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1 text-sm text-gray-500 min-h-[44px]"
      >
        ← Back
      </button>

      {/* Hero image */}
      {imageUrls.length > 0 && (
        <div className="rounded-xl overflow-hidden">
          <img
            src={imageUrls[0]}
            alt=""
            className="w-full h-56 object-cover cursor-pointer"
            loading="lazy"
            onClick={() => { setViewerStartIndex(0); setViewerOpen(true); }}
          />
          {imageUrls.length > 1 && (
            <div className="flex gap-2 overflow-x-auto bg-gray-100 p-2">
              {imageUrls.slice(1).map((url, i) => (
                <img
                  key={i}
                  src={url}
                  alt=""
                  className="h-16 w-24 object-cover rounded shrink-0 cursor-pointer"
                  loading="lazy"
                  onClick={() => { setViewerStartIndex(i + 1); setViewerOpen(true); }}
                />
              ))}
            </div>
          )}
        </div>
      )}
      {viewerOpen && imageUrls.length > 0 && (
        <ImageViewer
          images={imageUrls}
          startIndex={viewerStartIndex}
          onClose={() => setViewerOpen(false)}
        />
      )}

      {/* Header */}
      <div className="bg-white rounded-xl shadow p-4 space-y-1">
        <div className="flex items-start justify-between gap-2">
          <div>
            <span dir="rtl" className="block font-semibold text-gray-800">
              {(prop.neighborhood as string) || ''}
            </span>
            <span dir="rtl" className="block text-sm text-gray-500">
              {(prop.address_street as string) || ''}
            </span>
          </div>
          <div className="flex gap-1 shrink-0">
            <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">
              {source === 'yad2' ? 'Yad2' : source}
            </span>
            <span className={`${style.bg} text-white text-xs px-2 py-0.5 rounded-full font-medium`}>
              {style.icon} {style.label}
            </span>
          </div>
        </div>
        <div className="text-2xl font-bold text-gray-900">{formatPrice(price)}</div>
        <div className="text-sm text-gray-500 flex gap-3">
          {sqm && <span>{sqm}m²</span>}
          <span>{formatPricePerSqm(price, sqm)}</span>
        </div>
      </div>

      {/* Details */}
      <Section title="Details">
        <div className="grid grid-cols-3 gap-2">
          {amenities.map(a => (
            <div key={a.key} className="flex items-center gap-1 text-sm">
              <span className={a.active ? 'text-green-500' : 'text-gray-300'}>{a.active ? '✓' : '✗'}</span>
              <span className={a.active ? 'text-gray-800' : 'text-gray-400'}>{a.label}</span>
            </div>
          ))}
        </div>
        {isAgent && agentOffice && (
          <div className="text-sm text-gray-600 border-t pt-2 mt-2">
            Listed by: <span dir="rtl" className="font-medium">{agentOffice}</span>
          </div>
        )}
        {moveInDate && (
          <div className="text-sm text-gray-600">
            Move-in: <span className="font-medium">{formatDateFull(moveInDate)}</span>
          </div>
        )}
        <div className="mt-1">
          <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">
            {source === 'yad2' ? 'Yad2' : source}
          </span>
        </div>
      </Section>

      {/* Summary */}
      {summaryParts.length > 0 ? (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-800">
          {summaryParts.join(' + ')}
        </div>
      ) : null}

      {/* Signals */}
      <Section title="Signals">
        {hasTierSignals ? (
          <div className="space-y-3">
            {strongSignals.length > 0 && (
              <div>
                <div className="text-xs font-medium text-red-600 mb-1">Strong Signals</div>
                {strongSignals.map(s => (
                  <div key={s} className="text-sm text-gray-700 flex items-center gap-1">
                    <span className="text-red-500">●</span> {SIGNAL_LABELS[s] ?? s}
                  </div>
                ))}
              </div>
            )}
            {weakSignals.length > 0 && (
              <div>
                <div className="text-xs font-medium text-yellow-600 mb-1">Weak Signals</div>
                {weakSignals.map(s => (
                  <div key={s} className="text-sm text-gray-700 flex items-center gap-1">
                    <span className="text-yellow-500">●</span> {SIGNAL_LABELS[s] ?? s}
                  </div>
                ))}
              </div>
            )}
            {strongSignals.length === 0 && weakSignals.length === 0 && (
              <div className="text-sm text-gray-400">No signals detected</div>
            )}
          </div>
        ) : (
          <div className="space-y-1">
            <SignalRow label="Price Drop" active={priceDrops > 0} extra={priceDrops > 0 ? `${priceDrops}x` : undefined} />
            <SignalRow label="Reappeared" active={hasRelisting} />
            <SignalRow label="Days on Market" active={dom > 0} extra={`${dom} days`} />
            <SignalRow label="Price Stagnation" active={dom > 60 && priceDrops === 0} />
            <SignalRow label="Multiple Attempts" active={hasRelisting} extra={hasRelisting ? `${attempts} attempts` : undefined} />
            <SignalRow label="Text Changes" active={descChanges > 0} extra={descChanges > 0 ? `${descChanges}x` : undefined} />
            <SignalRow label="Image Changes" active={imgChanges > 0} extra={imgChanges > 0 ? `${imgChanges}x` : undefined} />
            <SignalRow label="Weak Language" active={weakLanguage.length > 0} />
            <SignalRow label="Condition" active={conditionKeywords.length > 0} />
            <SignalRow label="Relist Delay" active={hasRelisting} />
            <SignalRow label="Overexposure" active={dom > 90} />
          </div>
        )}
      </Section>

      {/* Property Evolution */}
      <Section title="Property Evolution">
        <div className="grid grid-cols-3 gap-3 text-center">
          <div>
            <div className="text-xs text-gray-400">First price</div>
            <div className="text-sm font-semibold text-gray-800">{formatPrice(firstPrice)}</div>
          </div>
          <div>
            <div className="text-xs text-gray-400">Current</div>
            <div className="text-sm font-semibold text-gray-800">{formatPrice(price)}</div>
          </div>
          <div>
            <div className="text-xs text-gray-400">Change</div>
            <div className={`text-sm font-semibold ${
              priceChange == null ? 'text-gray-400'
                : priceChange < 0 ? 'text-red-600'
                : priceChange > 0 ? 'text-green-600'
                : 'text-gray-600'
            }`}>
              {priceChange != null ? `${priceChange > 0 ? '+' : ''}${priceChange}%` : 'N/A'}
            </div>
          </div>
        </div>
        <div className="text-sm text-gray-600 border-t pt-2 mt-1">
          Listing attempts: <span className="font-medium">{attempts}</span>
        </div>
        {yad2DateAdded && (
          <div className="text-xs text-gray-400">
            Listed on Yad2: {formatDateFull(yad2DateAdded)} · Days on market: {dom} (from Yad2 data)
          </div>
        )}
        {!yad2DateAdded && !!prop.first_seen && (
          <div className="text-xs text-gray-400">
            First seen: {formatDate(prop.first_seen as string)}
          </div>
        )}
      </Section>

      {/* Listing Description */}
      {!!(prop.description) && (
        <Section title="Listing Description">
          <p dir="rtl" className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
            {conditionKeywords.length > 0
              ? highlightKeywords(String(prop.description), conditionKeywords)
              : String(prop.description)}
          </p>
        </Section>
      )}

      {/* Contact Info */}
      <Section title="Contact">
        <div className="text-sm space-y-1">
          {!!(prop.contact_name) && (
            <div className="text-gray-800">
              <span className="text-gray-500">Name: </span>
              <span dir="rtl" className="font-medium">{String(prop.contact_name)}</span>
            </div>
          )}
          {isAgent && agentOffice && (
            <div className="text-gray-800">
              <span className="text-gray-500">Agency: </span>
              <span dir="rtl" className="font-medium">{agentOffice}</span>
            </div>
          )}
          {!prop.contact_name && !agentOffice && (
            <div className="text-gray-400 text-xs">No contact info available from listing feed</div>
          )}
        </div>
      </Section>

      {/* Lifecycle Timeline */}
      <Section title="Timeline">
        <LifecycleTimeline events={events} />
      </Section>

      {/* Operator Input */}
      <Section title="Operator Input">
        <OperatorInputForm yad2Id={yad2Id!} />
      </Section>

      {/* Notes */}
      <Section title="Notes">
        <NotesList yad2Id={yad2Id!} notes={notes} />
      </Section>

      {/* Matches */}
      {matches.length > 0 && (
        <Section title="Duplicates Detected">
          <div className="space-y-2">
            {matches.map((m) => {
              const tier = m.match_tier as number;
              const matched = m.matched_property as Record<string, unknown> | null;
              const tierBadge =
                tier === 0
                  ? <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full font-medium">Same landlord</span>
                  : tier === 1
                  ? <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium">Same building</span>
                  : tier === 2
                  ? <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-medium">Similar property</span>
                  : <span className="text-xs bg-gray-50 text-gray-400 px-2 py-0.5 rounded-full font-medium">Possible match</span>;

              return (
                <div key={m.id as number} className="flex items-center justify-between gap-2 text-sm">
                  <div dir="rtl" className="text-gray-700 truncate">
                    {matched
                      ? (matched.address_street as string) || (matched.yad2_id as string)
                      : '—'}
                  </div>
                  {tierBadge}
                </div>
              );
            })}
          </div>
        </Section>
      )}

      {/* Action Buttons */}
      <div className="space-y-2 pb-8">
        <div className="flex gap-2">
          <button
            onClick={() => isFavorited ? removeFav.mutate(yad2Id!) : addFav.mutate(yad2Id!)}
            disabled={addFav.isPending || removeFav.isPending}
            className={`flex-1 min-h-[44px] rounded-lg text-sm font-medium border transition-colors disabled:opacity-50 ${
              isFavorited
                ? 'bg-yellow-50 border-yellow-300 text-yellow-700'
                : 'bg-white border-gray-300 text-gray-700'
            }`}
          >
            {isFavorited ? '⭐ Saved' : '☆ Save'}
          </button>
          <button
            onClick={() => isWhitelisted ? removeWhitelist.mutate(yad2Id!) : whitelist.mutate(yad2Id!)}
            disabled={whitelist.isPending || removeWhitelist.isPending}
            className={`flex-1 min-h-[44px] rounded-lg text-sm font-medium border transition-colors disabled:opacity-50 ${
              isWhitelisted
                ? 'bg-green-50 border-green-300 text-green-700'
                : 'bg-white border-gray-300 text-gray-700'
            }`}
          >
            {isWhitelisted ? '✓ Whitelisted' : 'Whitelist'}
          </button>
          <button
            onClick={() => isBlacklisted ? removeBlacklist.mutate(yad2Id!) : blacklist.mutate(yad2Id!)}
            disabled={blacklist.isPending || removeBlacklist.isPending}
            className={`flex-1 min-h-[44px] rounded-lg text-sm font-medium border transition-colors disabled:opacity-50 ${
              isBlacklisted
                ? 'bg-red-50 border-red-300 text-red-700'
                : 'bg-white border-gray-300 text-gray-700'
            }`}
          >
            {isBlacklisted ? '✗ Blacklisted' : 'Blacklist'}
          </button>
        </div>
        {!!prop.listing_url && (
          <button
            onClick={() => window.open(prop.listing_url as string, '_blank')}
            className="w-full min-h-[44px] bg-gray-900 text-white rounded-lg text-sm font-medium"
          >
            Open Source →
          </button>
        )}
      </div>
    </div>
  );
}
