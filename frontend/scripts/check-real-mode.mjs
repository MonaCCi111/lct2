import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import assert from 'node:assert/strict';
import { once } from 'node:events';

let v1Requests = 0;
const v2Requests = [];
const backend = createServer((request, response) => {
  response.setHeader('Access-Control-Allow-Origin', '*');
  response.setHeader('Content-Type', 'application/json');
  if (request.url === '/api/v1/system') {
    v1Requests += 1;
    response.end(JSON.stringify({ status: 'degraded', updated_at: '2026-09-20T15:42:00Z' }));
  } else if (request.url === '/api/v2/meta') {
    v2Requests.push(request.url);
    response.end(
      JSON.stringify({
        contract_version: 'dispatcher_api_v1',
        data_version: 'ml_handoff_v1',
        data_cutoff: '2026-06-30T23:59:59',
        source_timezone_known: false,
        real_feedback_available: false,
        live_ingestion_available: false,
      }),
    );
  } else if (request.url?.startsWith('/api/v2/objects')) {
    v2Requests.push(request.url);
    response.end(JSON.stringify({ items: [], next_cursor: null }));
  } else if (request.url?.startsWith('/api/v2/drafts')) {
    v2Requests.push(request.url);
    response.statusCode = 503;
    response.end(
      JSON.stringify({ code: 'backend_unavailable', message: 'Реальный API v2 недоступен.', details: null }),
    );
  } else {
    response.statusCode = 404;
    response.end('{}');
  }
});
backend.listen(0, '127.0.0.1');
await once(backend, 'listening');
const apiPort = backend.address().port;
const port = 5174;
const server = spawn(
  process.execPath,
  ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', String(port), '--strictPort'],
  {
    env: {
      ...process.env,
      VITE_ENABLE_MOCKS: 'false',
      VITE_API_BASE_URL: `http://127.0.0.1:${apiPort}/api/v1`,
      VITE_API_V2_BASE_URL: `http://127.0.0.1:${apiPort}/api/v2`,
    },
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  },
);
const serverReady = new Promise((resolve, reject) => {
  const timeout = setTimeout(() => reject(new Error('Vite did not start')), 15_000);
  server.stdout.on('data', (chunk) => {
    if (chunk.toString().includes('Local:')) {
      clearTimeout(timeout);
      resolve();
    }
  });
  server.on('exit', (code) => {
    clearTimeout(timeout);
    reject(new Error(`Vite exited: ${code}`));
  });
  server.stderr.on('data', (chunk) => process.stderr.write(chunk));
});
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
try {
  await serverReady;
  const page = await browser.newPage({ timezoneId: 'America/Los_Angeles', locale: 'ru-RU' });
  page.setDefaultTimeout(10_000);
  await page.goto(`http://127.0.0.1:${port}/overview`);
  await page.getByText('API: сбой сервиса', { exact: true }).waitFor();
  await page.getByRole('region', { name: 'Сводка инфраструктуры' }).getByRole('alert').waitFor();
  assert.equal(await page.locator('.topbar-time').count(), 0);
  await page.getByRole('button', { name: 'Состояние системы', exact: true }).click();
  await page.getByRole('dialog').getByText('20.09.2026, 18:42 МСК', { exact: true }).waitFor();
  await page.keyboard.press('Escape');
  assert.ok(v1Requests > 0, 'Real HTTP API v1 must receive the request');
  assert.equal(await page.evaluate(async () => (await navigator.serviceWorker.getRegistrations()).length), 0);

  await page.goto(`http://127.0.0.1:${port}/review`);
  await page.getByRole('heading', { name: 'Очередь проверки' }).waitFor();
  await page.getByText('Реальный API v2 недоступен.', { exact: true }).waitFor();
  assert.ok(
    v2Requests.some((url) => url === '/api/v2/meta'),
    'Real HTTP API v2 must receive Meta',
  );
  assert.ok(
    v2Requests.some((url) => url.startsWith('/api/v2/objects')),
    'Real HTTP API v2 must receive objects',
  );
  assert.ok(
    v2Requests.some((url) => url.startsWith('/api/v2/drafts')),
    'Real HTTP API v2 must receive drafts',
  );
  assert.equal(await page.getByText('ДУ объект Кси', { exact: true }).count(), 0);

  const v2Route = `http://127.0.0.1:${apiPort}/api/v2/**`;
  await page.route(v2Route, (route) => route.abort('connectionrefused'));
  await page.goto(`http://127.0.0.1:${port}/overview`);
  await page.goto(`http://127.0.0.1:${port}/review`);
  await page
    .getByText('Не удалось подключиться к API v2. Проверьте соединение.', { exact: true })
    .first()
    .waitFor();
  await page.unroute(v2Route);

  await page.goto(`http://127.0.0.1:${port}/foundation`);
  await page.getByRole('heading', { name: 'Страница не найдена' }).waitFor();
  console.log(
    'PASS: mocks=false uses v1/v2 HTTP backends, exposes v2 backend and network errors, shows no mock fallback, keeps Moscow timestamps in Los Angeles browser, unregisters MSW, and hides the foundation route.',
  );
} finally {
  await browser.close();
  server.kill();
  backend.closeAllConnections();
  backend.close();
}
