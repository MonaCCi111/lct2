import { Component, type ErrorInfo, type ReactNode } from 'react';
import { ErrorState } from './States';
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Dolos render error', error, info.componentStack);
  }
  render() {
    return this.state.failed ? (
      <main className="fatal-error">
        <ErrorState
          message="Ошибка интерфейса. Перезагрузите страницу."
          onRetry={() => window.location.reload()}
        />
      </main>
    ) : (
      this.props.children
    );
  }
}
