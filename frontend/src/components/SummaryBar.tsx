import { useStats, usePresetStats } from '../api/queries';

function formatTimeAgo(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

interface StatCardProps {
  label: string;
  value: string | number;
  onClick?: () => void;
  active?: boolean;
}

function StatCard({ label, value, onClick, active }: StatCardProps) {
  return (
    <div
      onClick={onClick}
      className={`flex-1 basis-0 rounded-lg shadow py-3 px-1 flex flex-col items-center justify-center ${
        onClick ? 'cursor-pointer hover:shadow-md transition-all' : ''
      } ${active ? 'bg-gray-900' : 'bg-white'}`}
    >
      <div className={`text-xl font-bold ${active ? 'text-white' : 'text-gray-900'}`}>{value}</div>
      <div className={`text-[10px] leading-tight mt-1 ${active ? 'text-gray-300' : 'text-gray-500'}`}>{label}</div>
    </div>
  );
}

interface SummaryBarProps {
  onStatClick?: (stat: string) => void;
  activeFilter?: string | null;
  category?: string;
}

export default function SummaryBar({ onStatClick, activeFilter, category }: SummaryBarProps) {
  const { data: stats } = useStats(category);
  const { data: presetStats } = usePresetStats(category);

  const totalScanned = (stats?.total_properties as number) ?? 0;
  const lastScanAt = stats?.last_scan_at as string | undefined;

  const presets = (presetStats?.presets as Record<string, number>[]) ?? [];
  const opportunities = presets.reduce((sum, p) => sum + (p.opportunities ?? 0), 0);

  const eventsByType = (stats?.events_by_type as Record<string, number>) ?? {};
  const priceDrops = eventsByType['price_drop'] ?? 0;
  const reappeared = eventsByType['relisting'] ?? 0;

  return (
    <div className="space-y-2">
      {lastScanAt && (
        <div className="text-sm text-gray-600 font-medium text-center">
          Last scan: {formatTimeAgo(lastScanAt)}
        </div>
      )}
      <div className="flex gap-2 overflow-x-auto">
        <StatCard
          label="Scanned"
          value={totalScanned}
          onClick={() => onStatClick?.('fullscan')}
          active={activeFilter === 'fullscan'}
        />
        <StatCard
          label="Opportunities"
          value={opportunities}
          onClick={() => onStatClick?.('opportunities')}
          active={activeFilter === 'opportunities'}
        />
        <StatCard
          label="Price Drops"
          value={priceDrops}
          onClick={() => onStatClick?.('price_drop')}
          active={activeFilter === 'price_drop'}
        />
        <StatCard
          label="Reappeared"
          value={reappeared}
          onClick={() => onStatClick?.('relisting')}
          active={activeFilter === 'relisting'}
        />
      </div>
    </div>
  );
}
