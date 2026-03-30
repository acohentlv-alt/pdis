import { useNavigate } from 'react-router-dom';
import OpenSearchForm from '../components/OpenSearchForm';

export default function SearchPage() {
  const navigate = useNavigate();

  return (
    <div className="max-w-lg mx-auto px-4 py-4 space-y-4">
      <h1 className="text-xl font-bold text-gray-900">🔍 Open Search</h1>
      <p className="text-sm text-gray-500">
        Search Yad2 with custom criteria. Results will appear in Findings.
      </p>
      <OpenSearchForm onSuccess={() => navigate('/search/results')} />
    </div>
  );
}
