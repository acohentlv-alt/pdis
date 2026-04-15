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
  colorClass?: string;
  activeColorClass?: string;
}

function StatCard({ label, value, onClick, active, colorClass = 'text-gray-900', activeColorClass = 'bg-gray-900' }: StatCardProps) {
  return (
    <div
      onClick={onClick}
      className={`flex-1 basis-0 rounded-2xl py-4 px-2 flex flex-col items-center justify-center transition-all ${
        onClick ? 'cursor-pointer active:scale-[0.97]' : ''
      } ${
        active
          ? `${activeColorClass} shadow-lg shadow-gray-900/20`
          : 'bg-white shadow-sm border border-gray-100 hover:border-gray-300 hover:shadow-md'
      }`}
    >
      <div className={`text-2xl font-bold tracking-tight tabular-nums ${active ? 'text-white' : colorClass}`}>{value}</div>
      <div className={`text-[10px] uppercase tracking-wider font-semibold leading-tight mt-1 ${active ? 'text-white/70' : 'text-gray-500'}`}>{label}</div>
    </div>
  );
}

interface SummaryBarProps {
  scanned: number;
  priceDrops: number;
  reappeared: number;
  onStatClick?: (stat: string) => void;
  activeFilter?: string | null;
  lastScanAt?: string;
}

export default function SummaryBar({ scanned, priceDrops, reappeared, onStatClick, activeFilter, lastScanAt }: SummaryBarProps) {
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
          value={scanned}
          onClick={() => onStatClick?.('scanned')}
          active={activeFilter === null || activeFilter === 'scanned'}
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
