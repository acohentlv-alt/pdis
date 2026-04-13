export function signalCount(sd: any): number {
  if (!sd) return 0;
  return (
    (sd.strong_signals?.length ?? 0) +
    (sd.weak_signals?.length ?? 0) +
    (sd.buyer_fit_tags?.length ?? 0)
  );
}
