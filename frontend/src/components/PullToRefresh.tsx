import { useRef, useState, type ReactNode, type TouchEvent } from 'react';

interface PullToRefreshProps {
  onRefresh: () => Promise<void> | void;
  children: ReactNode;
  threshold?: number;
}

export default function PullToRefresh({ onRefresh, children, threshold = 70 }: PullToRefreshProps) {
  const [pullDistance, setPullDistance] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [animating, setAnimating] = useState(false);
  const startY = useRef<number | null>(null);

  function handleTouchStart(e: TouchEvent) {
    if (window.scrollY > 0 || refreshing) return;
    startY.current = e.touches[0].clientY;
    setAnimating(false);
  }

  function handleTouchMove(e: TouchEvent) {
    if (startY.current === null || refreshing) return;
    const distance = e.touches[0].clientY - startY.current;
    if (distance > 0) {
      // Damped resistance — feels more native iOS
      setPullDistance(Math.min(distance * 0.5, 120));
    }
  }

  async function handleTouchEnd() {
    if (startY.current === null || refreshing) {
      startY.current = null;
      return;
    }
    startY.current = null;
    setAnimating(true);
    if (pullDistance >= threshold) {
      setRefreshing(true);
      setPullDistance(0);
      try {
        await onRefresh();
      } finally {
        setRefreshing(false);
      }
    } else {
      setPullDistance(0);
    }
  }

  const pulledEnough = pullDistance >= threshold;
  const indicatorHeight = refreshing ? 50 : pullDistance;
  const indicatorOpacity = refreshing ? 1 : Math.min(pullDistance / threshold, 1);
  const rotation = pulledEnough ? 180 : (pullDistance / threshold) * 180;

  return (
    <div
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      <div
        className={`flex justify-center items-center overflow-hidden ${animating ? 'transition-all duration-200 ease-out' : ''}`}
        style={{
          height: indicatorHeight,
          opacity: indicatorOpacity,
        }}
      >
        {refreshing ? (
          <div className="w-6 h-6 border-2 border-gray-900 border-t-transparent rounded-full animate-spin" />
        ) : (
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="text-gray-500 transition-transform duration-150"
            style={{ transform: `rotate(${rotation}deg)` }}
          >
            <line x1="12" y1="5" x2="12" y2="19" />
            <polyline points="19 12 12 19 5 12" />
          </svg>
        )}
      </div>
      {children}
    </div>
  );
}
