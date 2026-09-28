// Browser checks import this module explicitly; production UI never selects scenarios.
import { delay, http, HttpResponse } from 'msw';
import type { SetupWorker } from 'msw/browser';
import { apiConfig } from '../client/config';
import { analyticsFixtures, emptyAnalytics } from './analytics';
export function setAnalyticsScenario(worker: SetupWorker, state: 'error' | 'loading' | 'empty') {
  worker.use(
    http.get(`${apiConfig.baseUrl}/analytics/summary`, async ({ request }) => {
      const requested = new URL(request.url).searchParams.get('range');
      const range = requested === '24h' || requested === '30d' ? requested : '7d';
      if (state === 'error')
        return HttpResponse.json({ message: 'Агрегат временно недоступен.' }, { status: 503 });
      if (state === 'loading') await delay(5000);
      return HttpResponse.json(state === 'empty' ? emptyAnalytics(range) : analyticsFixtures[range]);
    }),
  );
}
