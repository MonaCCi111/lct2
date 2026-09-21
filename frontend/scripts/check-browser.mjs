import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';

const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
const context = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  colorScheme: 'dark',
  locale: 'ru-RU',
  timezoneId: 'Asia/Tokyo',
});
const page = await context.newPage();
page.setDefaultTimeout(10_000);
const failures = [];
const overviewApiRequests = [];
page.on('pageerror', (error) => failures.push(error.message));
const recordRequest = (request) => overviewApiRequests.push(new URL(request.url()).pathname);
const origin = process.env.TEST_BASE_URL || 'http://127.0.0.1:5173';
await mkdir('test-results', { recursive: true });
try {
  page.on('request', recordRequest);
  await page.goto(origin);
  await page.waitForURL('**/overview');
  await page.getByText('Демо API доступен').waitFor();
  await page.getByRole('heading', { name: 'Оперативный центр', exact: true }).waitFor();
  await page.getByText('Показано 24 из 24 загруженных', { exact: true }).waitFor();
  assert.match(await page.locator('.overview-update').innerText(), /20\.09\.2026, 18:42 МСК/);
  assert.equal(
    overviewApiRequests.some((path) => path.endsWith('/dashboard/summary')),
    true,
  );
  page.off('request', recordRequest);
  // Verify the aggregate transport independently of its presentation.
  const summary = await page.evaluate(async () => {
    const { apiGet } = await import('/src/api/client/http.ts');
    return apiGet('/dashboard/summary');
  });
  assert.equal(summary.channels.total, 12480);
  assert.equal(summary.predictions.active, 137);
  assert.equal(summary.channels.coverage_percent, 80);
  const formatted = await page.evaluate(async () => {
    const { formatDateTime } = await import('/src/utils/formatters.ts');
    return formatDateTime('2026-09-20T15:42:00Z');
  });
  assert.equal(formatted, '20.09.2026, 18:42 МСК');
  assert.equal(await page.locator('.sidebar').evaluate((el) => el.getBoundingClientRect().width), 224);
  assert.equal(await page.locator('.topbar').evaluate((el) => el.getBoundingClientRect().height), 52);
  await page.screenshot({ path: 'test-results/overview-1920.png', fullPage: true });
  const routes = [
    ['/overview', 'Оперативный центр'],
    ['/objects', 'Объекты'],
    ['/objects/101', 'Технический блок № 1'],
    ['/predictions', 'Прогнозы'],
    ['/predictions/TEMP-001', 'Прогноз TEMP-001'],
    ['/tickets', 'Наряды'],
    ['/analytics', 'Аналитика'],
  ];
  for (const [route, heading] of routes) {
    await page.goto(`${origin}${route}`);
    await page.getByRole('heading', { name: heading, exact: true }).waitFor();
    assert.equal(await page.locator('main').count(), 1);
  }
  await page
    .getByRole('navigation', { name: 'Основная навигация' })
    .getByRole('link', { name: 'Объекты', exact: true })
    .click();
  await page.waitForURL('**/objects');
  await page.getByRole('heading', { name: 'Объекты', exact: true }).waitFor();
  assert.equal(
    await page.getByRole('link', { name: 'Объекты', exact: true }).getAttribute('aria-current'),
    'page',
  );
  await page.getByRole('button', { name: 'Состояние системы', exact: true }).click();
  await page.getByRole('dialog').waitFor();
  await page.keyboard.press('Escape');
  assert.equal(await page.getByRole('dialog').count(), 0);
  assert.equal(
    await page
      .getByRole('button', { name: 'Состояние системы', exact: true })
      .evaluate((el) => el === document.activeElement),
    true,
  );
  await page.goto(`${origin}/foundation`);
  const temperature = page.getByRole('row').filter({ hasText: 'Температура шкафа управления' });
  await temperature.waitFor();
  assert.match(await temperature.innerText(), /46\s*%/);
  assert.match(await temperature.innerText(), /Критический/);
  const unsupported = page.getByRole('row').filter({ hasText: 'Дверь технического помещения' });
  assert.match(await unsupported.innerText(), /ML-анализ недоступен/);
  assert.doesNotMatch(await unsupported.innerText(), /Низкий|99|1\s*%/);
  await page.screenshot({ path: 'test-results/fixtures-1920.png', fullPage: true });
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.screenshot({ path: 'test-results/fixtures-1366.png', fullPage: true });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.getByRole('tab', { name: 'Компоненты', exact: true }).click();
  const workflowStyles = await page.locator('.workflow-status').evaluateAll((elements) =>
    elements.map((element) => {
      const style = getComputedStyle(element);
      return {
        radius: style.borderRadius,
        border: style.borderTopWidth,
        fontSize: style.fontSize,
        fontWeight: style.fontWeight,
        background: style.backgroundColor,
      };
    }),
  );
  assert.equal(workflowStyles.length, 4);
  for (const style of workflowStyles) {
    assert.deepEqual(style, {
      radius: '4px',
      border: '1px',
      fontSize: '12px',
      fontWeight: '500',
      background: 'rgb(37, 40, 45)',
    });
  }
  await page.getByRole('button', { name: 'Открыть параметры', exact: true }).click();
  await page.getByRole('dialog').waitFor();
  await page.keyboard.press('Tab');
  assert.equal(await page.getByRole('dialog').evaluate((el) => el.contains(document.activeElement)), true);
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Открыть пример меню' }).click();
  await page.getByRole('menuitem', { name: 'Открыть панель' }).click();
  await page.getByRole('dialog').waitFor();
  await page.keyboard.press('Escape');
  await page.getByLabel('Состояние', { exact: true }).selectOption('error');
  await page.getByRole('button', { name: 'Повторить' }).click();
  await page.getByText('Данные успешно загружены.').waitFor();
  await page.screenshot({ path: 'test-results/components-1366.png', fullPage: true });
  await page.goto(`${origin}/overview`);
  await page.getByRole('heading', { name: 'Оперативный центр', exact: true }).waitFor();
  await page.screenshot({ path: 'test-results/overview-1366.png', fullPage: true });
  await page.setViewportSize({ width: 800, height: 900 });
  assert.equal(await page.locator('.sidebar').evaluate((el) => el.getBoundingClientRect().width), 64);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.goto(`${origin}/unknown`);
  await page.getByRole('heading', { name: 'Страница не найдена' }).waitFor();
  assert.deepEqual(failures, []);
  console.log(
    'PASS: routes, navigation, MSW summary, Moscow time in Tokyo browser, operational overview, fixtures, responsive widths, drawer focus, menu, states; no page errors.',
  );
} catch (error) {
  await page.screenshot({ path: 'test-results/failure.png', fullPage: true });
  throw error;
} finally {
  await browser.close();
}
