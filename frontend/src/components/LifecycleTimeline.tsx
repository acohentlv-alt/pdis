import { EVENT_LABELS, formatDate, formatPrice } from '../lib/format';

interface LifecycleTimelineProps {
  events: Record<string, unknown>[];
}

const EVENT_COLORS: Record<string, string> = {
  price_drop: 'bg-red-500',
  price_increase: 'bg-blue-400',
  relisting: 'bg-orange-400',
  removal: 'bg-gray-400',
  new_listing: 'bg-green-500',
  description_change: 'bg-purple-400',
  image_change: 'bg-indigo-400',
};

export default function LifecycleTimeline({ events }: LifecycleTimelineProps) {
  // API returns DESC, reverse to chronological
  const chronological = [...events].reverse();

  if (chronological.length === 0) {
    return <p className="text-sm text-gray-400">No events recorded.</p>;
  }

  return (
    <div className="space-y-2">
      {chronological.map((ev) => {
        const type = ev.event_type as string;
        const dotColor = EVENT_COLORS[type] ?? 'bg-gray-300';
        const label = EVENT_LABELS[type] ?? type;
        const date = ev.created_at ? formatDate(ev.created_at as string) : '';
        const isPriceEvent = type === 'price_drop' || type === 'price_increase';
        const newVal = ev.new_value as string | null;

        return (
          <div key={ev.id as number} className="flex items-start gap-3">
            <div className={`mt-1 w-2.5 h-2.5 rounded-full shrink-0 ${dotColor}`} />
            <div className="flex-1 text-sm">
              <span className="font-medium text-gray-800">{label}</span>
              {isPriceEvent && newVal && (
                <span className="text-gray-500 ml-1">
                  — {formatPrice(parseInt(newVal, 10))}
                </span>
              )}
            </div>
            {date && <span className="text-xs text-gray-400 shrink-0">{date}</span>}
          </div>
        );
      })}
    </div>
  );
}
