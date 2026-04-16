import { useNavigate } from 'react-router-dom';
import OpenSearchForm from '../components/OpenSearchForm';

export default function SearchPage() {
  const navigate = useNavigate();

  function handleSubmit(params: Record<string, string | number>) {
    const urlParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      urlParams.set(key, String(value));
    }
    navigate(`/?custom=${encodeURIComponent(urlParams.toString())}`);
  }

  return (
    <div className="max-w-lg mx-auto px-4 py-4 space-y-4">
      <h1 className="text-xl font-bold text-gray-900">Open Search</h1>
      <p className="text-sm text-gray-500">
        Search with custom criteria. Results will appear on the Home screen.
      </p>
      <OpenSearchForm onSubmit={handleSubmit} />
    </div>
  );
}
