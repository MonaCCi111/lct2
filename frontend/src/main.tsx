import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './app/App';
import { apiConfig } from './api/client/config';
import { ErrorState } from './components/feedback/States';
import './styles/globals.css';
const container = document.getElementById('root');
if (!container) throw new Error('Root element is missing');
const root = createRoot(container);
async function bootstrap() {
  if (apiConfig.enableMocks) {
    const { worker } = await import('./api/mocks/browser');
    await worker.start({ onUnhandledRequest: 'bypass', quiet: true });
  } else if ('serviceWorker' in navigator) {
    // Remove only this app's MSW registration when switching back to real API.
    const registrations = await navigator.serviceWorker.getRegistrations();
    await Promise.all(
      registrations
        .filter(
          (registration) =>
            registration.active?.scriptURL === new URL('/mockServiceWorker.js', location.origin).href,
        )
        .map((registration) => registration.unregister()),
    );
  }
  root.render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
void bootstrap().catch(() =>
  root.render(
    <main className="fatal-error">
      <ErrorState
        message="Не удалось запустить приложение. Проверьте настройки mock API и перезагрузите страницу."
        onRetry={() => location.reload()}
      />
    </main>,
  ),
);
