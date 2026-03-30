import { Routes, Route } from 'react-router-dom';
import NavBar from './components/NavBar';
import HomePage from './pages/HomePage';
import SearchPage from './pages/SearchPage';
import SearchResultsPage from './pages/SearchResultsPage';
import PropertyDetailPage from './pages/PropertyDetailPage';

export default function App() {
  return (
    <div className="pb-16">
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/search/results" element={<SearchResultsPage />} />
        <Route path="/property/:yad2Id" element={<PropertyDetailPage />} />
      </Routes>
      <NavBar />
    </div>
  );
}
