import { Routes, Route, Navigate } from 'react-router-dom';
import NavBar from './components/NavBar';
import OpportunityPage from './pages/OpportunityPage';
import FavoritesPage from './pages/FavoritesPage';
import SearchPage from './pages/SearchPage';
import SearchResultsPage from './pages/SearchResultsPage';
import PropertyDetailPage from './pages/PropertyDetailPage';

export default function App() {
  return (
    <div className="pb-16">
      <Routes>
        <Route path="/" element={<Navigate to="/rent" replace />} />
        <Route path="/rent" element={<OpportunityPage category="rent" />} />
        <Route path="/buy" element={<OpportunityPage category="forsale" />} />
        <Route path="/listings" element={<FavoritesPage />} />
        <Route path="/favorites" element={<Navigate to="/listings" replace />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/search/results" element={<SearchResultsPage />} />
        <Route path="/property/:yad2Id" element={<PropertyDetailPage />} />
      </Routes>
      <NavBar />
    </div>
  );
}
