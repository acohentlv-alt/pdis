import { useStats, usePresetStats } from '../api/queries';

interface StatCardProps {
  label: string;
  value: string | number;
}

function StatCard({ label, value }: StatCardProps) {
  return (
    <div className="flex-1 bg-white rounded-lg shadow p-3 text-center min-w-0">
      <div className="text-xl font-bold text-gray-900">{value}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  );
}

export default function SummaryBar() {
  const { data: stats } = useStats();
  const { data: presetStats } = usePresetStats();

  const totalScanned = (stats?.total_properties as number) ?? 0;

  const presets = (presetStats?.presets as Record<string, number>[]) ?? [];
  const opportunities = presets.reduce((sum, p) => sum + (p.opportunities ?? 0), 0);
  const priceDrops = presets.reduce((sum, p) => sum + (p.price_drops ?? 0), 0);

  const ratio = totalScanned > 0 ? Math.round((opportunities / totalScanned) * 100) : 0;

  const eventsByType = (stats?.events_by_type as Record<string, number>) ?? {};
  const reappeared = eventsByType['relisting'] ?? 0;

  return (
    <div className="flex gap-2 overflow-x-auto py-2">
      <StatCard label="Scanned" value={totalScanned} />
      <StatCard label="Opportunities" value={opportunities} />
      <StatCard label="Ratio" value={`${ratio}%`} />
      <StatCard label="Price Drops" value={priceDrops} />
      <StatCard label="Reappeared" value={reappeared} />
    </div>
  );
}
