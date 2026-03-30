interface SignalBadgeProps {
  label: string;
  active: boolean;
  icon?: string;
}

export default function SignalBadge({ label, active, icon }: SignalBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full font-medium ${
        active
          ? 'bg-green-100 text-green-800'
          : 'bg-gray-100 text-gray-400'
      }`}
    >
      {icon && <span>{icon}</span>}
      {label}
    </span>
  );
}
