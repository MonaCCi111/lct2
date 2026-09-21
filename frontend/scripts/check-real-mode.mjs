import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import assert from 'node:assert/strict';
import { once } from 'node:events';

let requests = 0;
const backend = createServer((request, response) => {
  response.setHeader('Access-Control-Allow-Origin', '*');
  response.setHeader('Content-Type', 'application/json');
  if (request.url === '/api/v1/system') {
    requests += 1;
    response.end(JSON.stringify({ status: 'degraded', updated_at: '2026-09-20T15:42:00Z' }));
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
  assert.ok(requests > 0, 'Real HTTP API must receive the request');
  assert.equal(await page.evaluate(async () => (await navigator.serviceWorker.getRegistrations()).length), 0);
  await page.goto(`http://127.0.0.1:${port}/foundation`);
  await page.getByRole('heading', { name: 'Страница не найдена' }).waitFor();
  console.log(
    'PASS: mocks=false uses HTTP backend, Moscow timestamps in Los Angeles browser, no MSW, foundation route hidden.',
  );
} finally {
  await browser.close();
  server.kill();
  backend.closeAllConnections();
  backend.close();
}
