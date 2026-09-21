import { lazy, Suspense } from 'react';
import { createBrowserRouter, Link, Navigate, useRouteError } from 'react-router-dom';
import { AppLayout } from '../layouts/AppLayout';
import { EmptyState, ErrorState, LoadingState } from '../../components/feedback/States';
import { apiConfig } from '../../api/client/config';
const OverviewPage = lazy(() => import('../../pages/overview/OverviewPage'));
const ObjectsPage = lazy(() => import('../../pages/objects/ObjectsPage'));
const ObjectWorkspacePage = lazy(() => import('../../pages/object-workspace/ObjectWorkspacePage'));
const PredictionsPage = lazy(() => import('../../pages/predictions/PredictionsPage'));
const PredictionInvestigationPage = lazy(
  () => import('../../pages/prediction-investigation/PredictionInvestigationPage'),
);
const TicketsPage = lazy(() => import('../../pages/tickets/TicketsPage'));
const AnalyticsPage = lazy(() => import('../../pages/analytics/AnalyticsPage'));
const FoundationPage = lazy(() => import('../../pages/foundation/FoundationPage'));
function RouteError() {
  const error = useRouteError();
  return (
    <main className="fatal-error">
      <ErrorState message={error instanceof Error ? error.message : 'Не удалось открыть страницу.'} />
      <a className="button button-secondary" href="/overview">
        В оперативный центр
      </a>
    </main>
  );
}
export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <Navigate to="/overview" replace /> },
      ...[
        { path: 'overview', Component: OverviewPage },
        { path: 'objects', Component: ObjectsPage },
        { path: 'objects/:objectId', Component: ObjectWorkspacePage },
        { path: 'predictions', Component: PredictionsPage },
        { path: 'predictions/:predictionId', Component: PredictionInvestigationPage },
        { path: 'tickets', Component: TicketsPage },
        { path: 'analytics', Component: AnalyticsPage },
        ...(apiConfig.enableMocks ? [{ path: 'foundation', Component: FoundationPage }] : []),
      ].map(({ path, Component }) => ({
        path,
        element: (
          <Suspense fallback={<LoadingState />}>
            <Component />
          </Suspense>
        ),
      })),
      {
        path: '*',
        element: (
          <EmptyState
            title="Страница не найдена"
            description="Проверьте адрес или вернитесь в рабочее пространство."
            action={
              <Link className="button button-secondary" to="/overview">
                В оперативный центр
              </Link>
            }
          />
        ),
      },
    ],
  },
]);
