import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import './index.css';
import App from './App';
import { ToastProvider } from './lib/toast';
import TelemetryErrorBoundary from './components/TelemetryErrorBoundary';
import { logEvent } from './lib/telemetry';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

// Global error handlers — registered before render so they catch boot-time errors too.
// StrictMode double-invokes in dev but addEventListener deduplicates identical handlers naturally.
window.addEventListener('error', (e) => {
  logEvent('js_error', {
    message: e.message,
    filename: e.filename,
    lineno: e.lineno,
    colno: e.colno,
  }, {}, 'error');
});
window.addEventListener('unhandledrejection', (e) => {
  logEvent('js_error', {
    message: String(e.reason),
    type: 'unhandled_rejection',
  }, {}, 'error');
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ToastProvider>
          <TelemetryErrorBoundary>
            <App />
          </TelemetryErrorBoundary>
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
