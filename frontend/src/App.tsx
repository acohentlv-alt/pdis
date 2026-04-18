import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useEffect, useRef } from 'react';
import NavBar from './components/NavBar';
import OpportunityPage from './pages/OpportunityPage';
import FavoritesPage from './pages/FavoritesPage';
import SearchPage from './pages/SearchPage';
import PropertyDetailPage from './pages/PropertyDetailPage';
import UxHealthPage from './pages/UxHealthPage';
import { logEvent } from './lib/telemetry';

export default function App() {
  // ALL hooks must be before any early return — React error #310 rule
  const location = useLocation();
  const lastPath = useRef<string | null>(null);

  useEffect(() => {
    if (lastPath.current !== location.pathname) {
      lastPath.current = location.pathname;
      logEvent('page_view', { path: location.pathname });
    }
  }, [location.pathname]);

  const hideNavBar = location.pathname.startsWith('/admin');

  return (
    <div className={hideNavBar ? undefined : 'pb-16'}>
      <Routes>
        <Route path="/" element={<OpportunityPage />} />
        <Route path="/rent" element={<Navigate to="/" replace />} />
        <Route path="/buy" element={<Navigate to="/" replace />} />
        <Route path="/listings" element={<FavoritesPage />} />
        <Route path="/favorites" element={<Navigate to="/listings" replace />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/property/:yad2Id" element={<PropertyDetailPage />} />
        <Route path="/admin/ux-health" element={<UxHealthPage />} />
      </Routes>
      {!hideNavBar && <NavBar />}
    </div>
  );
}
