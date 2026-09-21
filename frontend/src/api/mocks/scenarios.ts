// Browser-test controls, dynamically imported by scripts/check-*.mjs only.
import { delay, http, HttpResponse } from 'msw';
import type { SetupWorker } from 'msw/browser';
import { apiConfig } from '../client/config';
import { dashboardSummaryFixture } from './dashboard';
import { operationalPredictions, objectStatusFixtures } from './operational';
import { objectDetailFixtures, objectTopologyFixture, objectWorkspacePredictions } from './object-workspace';
export type DashboardEndpoint = '/dashboard/summary' | '/predictions' | '/objects/status-summary';
export function setDashboardScenario(
  worker: SetupWorker,
  path: DashboardEndpoint,
  state: 'error' | 'loading' | 'empty',
) {
  worker.use(
    http.get(`${apiConfig.baseUrl}${path}`, async () => {
      if (state === 'error')
        return HttpResponse.json(
          { message: 'Сервис временно недоступен. Повторите запрос.' },
          { status: 503 },
        );
      if (state === 'empty') return HttpResponse.json([]);
      await delay(5000);
      return HttpResponse.json(
        path === '/dashboard/summary'
          ? dashboardSummaryFixture
          : path === '/predictions'
            ? operationalPredictions
            : objectStatusFixtures,
      );
    }),
  );
}
export type ObjectWorkspaceEndpoint = 'detail' | 'topology' | 'predictions';
export function setObjectWorkspaceScenario(
  worker: SetupWorker,
  endpoint: ObjectWorkspaceEndpoint,
  state: 'error' | 'loading' | 'empty',
  objectId: number,
) {
  const detail = objectDetailFixtures.find((item) => item.object_id === objectId);
  const topology = objectTopologyFixture(objectId, detail?.object_name ?? String(objectId));
  const path =
    endpoint === 'predictions'
      ? '/predictions'
      : endpoint === 'topology'
        ? '/objects/:objectId/topology'
        : '/objects/:objectId';
  worker.use(
    http.get(`${apiConfig.baseUrl}${path}`, async () => {
      if (state === 'error')
        return HttpResponse.json(
          { message: 'Сервис временно недоступен. Повторите запрос.' },
          { status: 503 },
        );
      if (state === 'loading') await delay(5000);
      if (state === 'empty')
        return HttpResponse.json(
          endpoint === 'predictions' ? [] : { ...topology, piket_min: null, piket_max: null, segments: [] },
        );
      return HttpResponse.json(
        endpoint === 'predictions'
          ? objectWorkspacePredictions.filter((item) => item.object_id === objectId)
          : endpoint === 'topology'
            ? topology
            : detail,
      );
    }),
  );
}
