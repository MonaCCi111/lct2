import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
const origin = process.env.TEST_BASE_URL || 'http://127.0.0.1:5173';
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
const errors = [];
await mkdir('test-results', { recursive: true });
async function configure(page, state, clear = false) {
  if (clear)
    await page
      .getByRole('navigation', { name: 'Основная навигация' })
      .getByRole('link', { name: 'Объекты', exact: true })
      .click();
  await page.evaluate(
    async ({ state, clear }) => {
      const urls = performance.getEntriesByType('resource').map((entry) => entry.name);
      const { worker } = await import(
        urls.findLast((url) => new URL(url).pathname === '/src/api/mocks/browser.ts')
      );
      worker.resetHandlers();
      if (state) {
        const { setAnalyticsScenario } = await import('/src/api/mocks/analytics-scenarios.ts');
        setAnalyticsScenario(worker, state);
      }
      if (clear) {
        const { queryClient } = await import(
          urls.findLast((url) => new URL(url).pathname === '/src/app/providers/AppProviders.tsx')
        );
        queryClient.removeQueries({ queryKey: ['analytics'] });
      }
    },
    { state, clear },
  );
  if (clear)
    await page
      .getByRole('navigation', { name: 'Основная навигация' })
      .getByRole('link', { name: 'Аналитика', exact: true })
      .click();
}
async function rangeReady(page, range) {
  await page
    .locator(`[data-testid="risk-timeline"][data-range="${range}"] .recharts-line-curve`)
    .first()
    .waitFor();
}
try {
  for (const theme of ['dark', 'light']) {
    const page = await browser.newPage({
      viewport: { width: 1920, height: 1080 },
      colorScheme: theme,
      timezoneId: 'America/Los_Angeles',
      locale: 'ru-RU',
    });
    page.setDefaultTimeout(15000);
    page.on('pageerror', (error) => errors.push(error.message));
    await page.goto(`${origin}/analytics`);
    await rangeReady(page, '7d');
    assert.equal(await page.getByLabel('Период аналитики').inputValue(), '7d');
    assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
    assert.match(await page.locator('.analytics-update').innerText(), /20\.09\.2026, 18:42 МСК/);
    assert.equal(await page.locator('.analytics-timeline .recharts-line-curve').count(), 3);
    assert.equal(await page.locator('.recharts-pie').count(), 0);
    assert.equal(
      await page.getByRole('table', { name: 'ML-покрытие по доменам' }).locator('tbody tr').count(),
      5,
    );
    assert.doesNotMatch(
      await page.locator('.analytics-page').innerText(),
      /MTTR|SLA|accuracy|precision|recall|ROC-AUC|F1|будущих аварий|ожидается.*отказов/i,
    );
    for (const [width, height] of [
      [1920, 1080],
      [1366, 768],
    ]) {
      await page.setViewportSize({ width, height });
      await page.waitForFunction(() => {
        const box = document.querySelector('.analytics-timeline .recharts-surface')?.getBoundingClientRect();
        return box?.width > 0;
      });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      const labels = await page
        .locator('.analytics-timeline .recharts-xAxis .recharts-cartesian-axis-tick-value')
        .evaluateAll((nodes) =>
          nodes.map((node) => {
            const r = node.getBoundingClientRect();
            return { left: r.left, right: r.right };
          }),
        );
      for (let i = 1; i < labels.length; i++)
        assert.ok(labels[i].left >= labels[i - 1].right, 'axis labels overlap');
      await page.screenshot({ path: `test-results/analytics-${theme}-${width}.png` });
    }
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.getByRole('table', { name: 'ML-покрытие по доменам' }).scrollIntoViewIfNeeded();
    await page.screenshot({ path: `test-results/analytics-coverage-${theme}.png` });
    await page.getByRole('heading', { name: 'Аналитика', exact: true }).scrollIntoViewIfNeeded();
    const curve7 = await page.locator('.analytics-timeline .recharts-line-curve').first().getAttribute('d');
    for (const range of ['24h', '30d']) {
      await page.getByLabel('Период аналитики').selectOption('7d');
      await rangeReady(page, '7d');
      await page.getByLabel('Период аналитики').selectOption(range);
      await rangeReady(page, range);
      assert.notEqual(
        await page.locator('.analytics-timeline .recharts-line-curve').first().getAttribute('d'),
        curve7,
      );
      assert.equal(
        await page.getByTestId('risk-timeline').getAttribute('data-points'),
        range === '24h' ? '13' : '16',
      );
      if (theme === 'dark') await page.screenshot({ path: `test-results/analytics-${range}.png` });
    }
    // Native select keyboard interaction, followed by a real mouse tooltip.
    await page.getByLabel('Период аналитики').focus();
    await page.keyboard.press('Home');
    await page.keyboard.press('Enter');
    await page.keyboard.press('Escape');
    await rangeReady(page, '24h');
    await page.getByLabel('Период аналитики').selectOption('7d');
    await rangeReady(page, '7d');
    const chart = await page.locator('.analytics-timeline .recharts-surface').boundingBox();
    await page.mouse.move(chart.x + chart.width - 30, chart.y + 90);
    await page.locator('.analytics-tooltip').waitFor();
    assert.match(await page.locator('.analytics-tooltip').innerText(), /МСК/);
    const tooltip = await page.locator('.analytics-tooltip').boundingBox();
    assert.ok(tooltip.x >= 0 && tooltip.x + tooltip.width <= 1920, 'tooltip clipped');
    await page.screenshot({ path: `test-results/analytics-tooltip-${theme}.png` });
    await page.mouse.move(5, 5);
    const row = page.getByRole('row', { name: 'объект Фита: открыть объект' });
    if (theme === 'dark') {
      await row.focus();
      await page.keyboard.press('Enter');
    } else await row.click();
    await page.waitForURL('**/objects/203');
    await page.getByRole('heading', { name: 'объект Фита', exact: true }).waitFor();
    await page
      .getByRole('navigation', { name: 'Основная навигация' })
      .getByRole('link', { name: 'Аналитика', exact: true })
      .click();
    await rangeReady(page, '7d');
    await configure(page, 'error');
    await page.getByRole('button', { name: 'Обновить аналитику' }).click();
    await page.getByText('Показаны сохранённые данные. Требуется обновление.').waitFor();
    await rangeReady(page, '7d');
    await page.getByLabel('Период аналитики').selectOption('24h');
    // Clear this cached range so the switch genuinely exercises placeholder/error behavior below.
    await configure(page, 'loading', true);
    await page.getByRole('status', { name: 'Загрузка аналитики' }).waitFor();
    await page.screenshot({ path: `test-results/analytics-loading-${theme}.png` });
    await rangeReady(page, '7d');
    await configure(page, 'loading');
    await page.getByLabel('Период аналитики').selectOption('24h');
    await page.getByText(/Показаны данные за 7 дней. Загружается период 24 ч/).waitFor();
    assert.equal(await page.getByTestId('risk-timeline').getAttribute('data-range'), '7d');
    await rangeReady(page, '24h');
    await configure(page, 'error');
    await page.getByLabel('Период аналитики').selectOption('30d');
    await page.getByText(/Показаны данные за 24 ч. Не удалось загрузить период 30 дней/).waitFor();
    assert.equal(await page.getByTestId('risk-timeline').getAttribute('data-range'), '24h');
    await configure(page, 'empty', true);
    await page.getByText('Аналитические данные отсутствуют').waitFor();
    await configure(page, 'error', true);
    await page.getByRole('alert').filter({ hasText: 'Не удалось загрузить аналитику.' }).waitFor();
    await configure(page, null);
    await page.getByRole('button', { name: 'Повторить', exact: true }).click();
    await rangeReady(page, '7d');
    await page.close();
  }
  assert.deepEqual(errors, []);
  console.log(
    'PASS Analytics: aggregate ranges, real chart changes, dark/light 1920/1366, Moscow tooltip, axes, keyboard, object navigation, loading/error/empty/stale and retained range.',
  );
} finally {
  await browser.close();
}
