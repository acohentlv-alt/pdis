import { useLocation, useNavigate } from 'react-router-dom';

const tabs = [
  { path: '/', icon: '🏠', label: 'Home' },
  { path: '/search', icon: '🔍', label: 'Search' },
  { path: '/search/results', icon: '📋', label: 'Findings' },
];

export default function NavBar() {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 z-50" style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}>
      <div className="max-w-lg mx-auto flex">
        {tabs.map(tab => {
          const isActive = tab.path === '/'
            ? location.pathname === '/'
            : location.pathname.startsWith(tab.path);
          return (
            <button
              key={tab.path}
              onClick={() => navigate(tab.path)}
              className={`flex-1 flex flex-col items-center py-2 text-xs ${
                isActive ? 'text-gray-900 font-semibold' : 'text-gray-400'
              }`}
            >
              <span className="text-xl">{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
