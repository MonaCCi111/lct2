import { lazy, Suspense } from 'react';
import { createBrowserRouter, Link, Navigate, useRouteError } from 'react-router-dom';
import { AppLayout } from '../layouts/AppLayout';
import { EmptyState, ErrorState, LoadingState } from '../../components/feedback/States';
import { apiConfig } from '../../api/client/config';
const OverviewPage = lazy(() => import('../../pages/overview/OverviewPage'));
const ObjectsPage = lazy(() => import('../../pages/objects/ObjectsPage'));
const ObjectWorkspacePage = lazy(() => import('../../pages/object-workspace/ObjectWorkspacePage'));
const PredictionsPage = lazy(() => import('../../pages/predictions/PredictionsPage'));
const ReviewPage = lazy(() => import('../../pages/review/ReviewPage'));
const ReviewDetailPage = lazy(() => import('../../pages/review/ReviewDetailPage'));
const WorkOrdersPage = lazy(() => import('../../pages/review/WorkOrdersPage'));
const WorkOrderDetailPage = lazy(() => import('../../pages/review/WorkOrderDetailPage'));
const PredictionInvestigationPage = lazy(
  () => import('../../pages/prediction-investigation/PredictionInvestigationPage'),
);
const TicketsPage = lazy(() => import('../../pages/tickets/TicketsPage'));
const AnalyticsPage = lazy(() => import('../../pages/analytics/AnalyticsPage'));
const FoundationPage = lazy(() => import('../../pages/foundation/FoundationPage'));
const HistoricalOverviewPage = lazy(() => import('../../pages/dispatcher/OverviewPage'));
const ChannelsPage = lazy(() => import('../../pages/dispatcher/InvestigationPages').then((m) => ({ default: m.ChannelsPage })));
const ChannelDetailPage = lazy(() => import('../../pages/dispatcher/InvestigationPages').then((m) => ({ default: m.ChannelDetailPage })));
const SituationsPage = lazy(() => import('../../pages/dispatcher/InvestigationPages').then((m) => ({ default: m.SituationsPage })));
const SituationDetailPage = lazy(() => import('../../pages/dispatcher/InvestigationPages').then((m) => ({ default: m.SituationDetailPage })));
const GroupQueuePage = lazy(() => import('../../pages/dispatcher/GroupAndQualityPages').then((m) => ({ default: m.GroupQueuePage })));
const GroupDetailPage = lazy(() => import('../../pages/dispatcher/GroupAndQualityPages').then((m) => ({ default: m.GroupDetailPage })));
const QualityPage = lazy(() => import('../../pages/dispatcher/GroupAndQualityPages').then((m) => ({ default: m.QualityPage })));
const FireHistoryPage = lazy(() => import('../../pages/dispatcher/FireAndReplayPages').then((m) => ({ default: m.FireHistoryPage })));
const ReplayPage = lazy(() => import('../../pages/dispatcher/FireAndReplayPages').then((m) => ({ default: m.ReplayPage })));
const HistoricalObjectsPage = lazy(() => import('../../pages/dispatcher/ObjectPages').then((m) => ({ default: m.ObjectsPage })));
const HistoricalObjectDetailPage = lazy(() => import('../../pages/dispatcher/ObjectPages').then((m) => ({ default: m.ObjectDetailPage })));
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
        { path: 'overview', Component: HistoricalOverviewPage },
        { path: 'objects', Component: HistoricalObjectsPage },
        { path: 'objects/:objectId', Component: HistoricalObjectDetailPage },
        { path: 'channels', Component: ChannelsPage },
        { path: 'channels/:channelId', Component: ChannelDetailPage },
        { path: 'situations', Component: SituationsPage },
        { path: 'situations/:situationId', Component: SituationDetailPage },
        { path: 'review', Component: GroupQueuePage },
        { path: 'review/groups', Component: GroupQueuePage },
        { path: 'review/groups/:groupId', Component: GroupDetailPage },
        { path: 'review/drafts', Component: ReviewPage },
        { path: 'review/work-orders', Component: WorkOrdersPage },
        { path: 'review/work-orders/:workOrderId', Component: WorkOrderDetailPage },
        { path: 'review/:draftId', Component: ReviewDetailPage },
        { path: 'analytics', Component: QualityPage },
        { path: 'fire-history', Component: FireHistoryPage },
        { path: 'replay', Component: ReplayPage },
        ...(apiConfig.enableMocks ? [
          { path: 'legacy/overview', Component: OverviewPage },
          { path: 'legacy/objects', Component: ObjectsPage },
          { path: 'legacy/predictions', Component: PredictionsPage },
          { path: 'legacy/tickets', Component: TicketsPage },
          { path: 'legacy/analytics', Component: AnalyticsPage },
          { path: 'legacy/objects/:objectId', Component: ObjectWorkspacePage },
          { path: 'legacy/predictions/:predictionId', Component: PredictionInvestigationPage },
        ] : []),
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
