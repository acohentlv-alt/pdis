import { Component, type ReactNode, type ErrorInfo } from 'react';
import { logEvent } from '../lib/telemetry';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export default class TelemetryErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    logEvent(
      'js_error',
      {
        message: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack,
      },
      {},
      'error'
    );
    this.setState({ hasError: true });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="text-center p-8">
            <p className="text-gray-700 text-lg font-medium mb-4">Something went wrong. Refresh to retry.</p>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-medium"
            >
              Refresh
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
