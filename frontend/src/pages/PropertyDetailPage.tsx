import { useNavigate, useParams } from 'react-router-dom';
import { useProperty, useSignals, useEvents, useOperatorInput, useMatches } from '../api/queries';
import { useWhitelist, useRemoveWhitelist, useBlacklist, useRemoveBlacklist } from '../api/mutations';
import { formatPrice, formatPricePerSqm, formatDate, formatDateFull, CLASSIFICATION_STYLES } from '../lib/format';
import LifecycleTimeline from '../components/LifecycleTimeline';
import OperatorInputForm from '../components/OperatorInputForm';
import NotesList from '../components/NotesList';

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

export default function PropertyDetailPage() {
  const { yad2Id } = useParams<{ yad2Id: string }>();
  const navigate = useNavigate();

  const { data: prop, isLoading } = useProperty(yad2Id);
  useSignals(yad2Id);
  const { data: eventsData } = useEvents(yad2Id);
  useOperatorInput(yad2Id);
  const { data: matchesData } = useMatches(yad2Id);

  const whitelist = useWhitelist(yad2Id!);
  const removeWhitelist = useRemoveWhitelist(yad2Id!);
  const blacklist = useBlacklist(yad2Id!);
  const removeBlacklist = useRemoveBlacklist(yad2Id!);

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

  // Signal details
  const priceDrops = (sd.price_drops as number) ?? 0;
  const hasRelisting = !!(sd.has_relisting);
  const descChanges = (sd.desc_changes as number) ?? 0;
  const imgChanges = (sd.img_changes as number) ?? 0;
  const weakLanguage = Array.isArray(sd.weak_language_found) ? sd.weak_language_found as unknown[] : [];

  // Summary line
  const summaryParts: string[] = [];
  if (hasRelisting) summaryParts.push('Returned after removal');
  if (priceDrops > 0) summaryParts.push('Price drop');
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
        onClick={() => navigate('/')}
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
            className="w-full h-56 object-cover"
            loading="lazy"
          />
          {imageUrls.length > 1 && (
            <div className="flex gap-2 overflow-x-auto bg-gray-100 p-2">
              {imageUrls.slice(1).map((url, i) => (
                <img
                  key={i}
                  src={url}
                  alt=""
                  className="h-16 w-24 object-cover rounded shrink-0"
                  loading="lazy"
                />
              ))}
            </div>
          )}
        </div>
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
            Listed by: <span className="font-medium">{agentOffice}</span>
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
      {summaryParts.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-800">
          {summaryParts.join(' + ')}
        </div>
      )}

      {/* Signals */}
      <Section title="Signals">
        <SignalRow label="Price Drop" active={priceDrops > 0} extra={priceDrops > 0 ? `${priceDrops}x` : undefined} />
        <SignalRow label="Reappeared" active={hasRelisting} />
        <SignalRow label="Days on Market" active={dom > 0} extra={`${dom} days`} />
        <SignalRow label="Price Stagnation" active={dom > 60 && priceDrops === 0} />
        <SignalRow label="Multiple Attempts" active={hasRelisting} extra={hasRelisting ? `${attempts} attempts` : undefined} />
        <SignalRow label="Text Changes" active={descChanges > 0} extra={descChanges > 0 ? `${descChanges}x` : undefined} />
        <SignalRow label="Image Changes" active={imgChanges > 0} extra={imgChanges > 0 ? `${imgChanges}x` : undefined} />
        <SignalRow label="Weak Language" active={weakLanguage.length > 0} />
        <SignalRow label="Relist Delay" active={hasRelisting} />
        <SignalRow label="Overexposure" active={dom > 90} />
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
        <Section title="Doublons détectés">
          <div className="space-y-2">
            {matches.map((m) => {
              const tier = m.match_tier as number;
              const matched = m.matched_property as Record<string, unknown> | null;
              const tierBadge =
                tier === 0
                  ? <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full font-medium">Même propriétaire</span>
                  : tier === 1
                  ? <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium">Même immeuble</span>
                  : tier === 2
                  ? <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-medium">Bien similaire</span>
                  : <span className="text-xs bg-gray-50 text-gray-400 px-2 py-0.5 rounded-full font-medium">Correspondance possible</span>;

              return (
                <div key={m.id as number} className="flex items-center justify-between gap-2 text-sm">
                  <div className="text-gray-700 truncate">
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
            onClick={() => isWhitelisted ? removeWhitelist.mutate() : whitelist.mutate()}
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
            onClick={() => isBlacklisted ? removeBlacklist.mutate() : blacklist.mutate()}
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
