import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
const page = await browser.newPage({
  viewport: { width: 1920, height: 1080 },
  colorScheme: 'dark',
  timezoneId: 'America/Los_Angeles',
  locale: 'ru-RU',
});
page.setDefaultTimeout(12_000);
const origin = process.env.TEST_BASE_URL || 'http://127.0.0.1:5173';
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));
await mkdir('test-results', { recursive: true });
const ready = async () => {
  await page.getByText('Показано 24 из 24 загруженных').waitFor();
  await page.getByText('Показано объектов: 8').waitFor();
  await page.getByText('80%', { exact: true }).waitFor();
};
async function scenario(path, state, clearCache = true) {
  // Navigate within the SPA so MSW overrides persist, then remount the dashboard.
  if (clearCache) {
    await page
      .getByRole('navigation', { name: 'Основная навигация' })
      .getByRole('link', { name: 'Аналитика', exact: true })
      .click();
    await page.getByRole('heading', { name: 'Аналитика', exact: true }).waitFor();
  }
  await page.evaluate(
    async ({ path, state, clearCache }) => {
      const { setDashboardScenario } = await import('/src/api/mocks/scenarios.ts');
      // Use the loaded module URLs, including Vite HMR versions, to target the app's instances.
      const resources = performance.getEntriesByType('resource').map((entry) => entry.name);
      const workerUrl = resources.findLast((url) => new URL(url).pathname === '/src/api/mocks/browser.ts');
      const { worker } = await import(workerUrl);
      worker.resetHandlers();
      setDashboardScenario(worker, path, state);
      if (clearCache) {
        const providerUrl = resources.findLast(
          (url) => new URL(url).pathname === '/src/app/providers/AppProviders.tsx',
        );
        const { queryClient } = await import(providerUrl);
        queryClient.clear();
      }
    },
    { path, state, clearCache },
  );
  if (clearCache)
    await page
      .getByRole('navigation', { name: 'Основная навигация' })
      .getByRole('link', { name: 'Оперативный центр', exact: true })
      .click();
}
try {
  await page.goto(`${origin}/overview`);
  await ready();
  assert.match(await page.locator('.overview-update').innerText(), /20\.09\.2026, 18:42 МСК/);
  const semanticStyles = await page
    .locator('.operational-workspace .semantic-indicator')
    .evaluateAll((elements) =>
      elements.map((element) => {
        const style = getComputedStyle(element);
        const urgency = element.classList.contains('urgency-indicator');
        // Risk keeps a single dot; urgency is a fixed-width group of small squares.
        const marker = element.querySelector(urgency ? '.urgency-squares' : '.semantic-marker');
        const markerStyle = getComputedStyle(marker);
        const square = element.querySelector('.urgency-square');
        return {
          background: style.backgroundColor,
          border: style.borderTopWidth,
          color: style.color,
          primary: getComputedStyle(document.documentElement).getPropertyValue('--text-primary').trim(),
          fontSize: style.fontSize,
          fontWeight: style.fontWeight,
          numeric: style.fontVariantNumeric,
          markerWidth: markerStyle.width,
          markerHeight: square ? getComputedStyle(square).height : markerStyle.height,
          markerRadius: square ? getComputedStyle(square).borderRadius : markerStyle.borderRadius,
          squares: element.querySelectorAll('.urgency-square').length,
          decorative: marker.getAttribute('aria-hidden'),
          urgency,
          label: element.textContent.trim(),
        };
      }),
    );
  assert.equal(semanticStyles.length, 56); // 24 risk + 24 urgency + eight object risks.
  for (const style of semanticStyles) {
    assert.equal(style.background, 'rgba(0, 0, 0, 0)');
    assert.equal(style.border, '0px');
    assert.equal(style.color, 'rgb(231, 232, 234)');
    assert.equal(style.fontSize, '12px');
    assert.equal(style.fontWeight, '500');
    assert.equal(style.numeric, 'tabular-nums');
    assert.equal(style.decorative, 'true');
    assert.ok(style.label.length > 0);
    assert.equal(style.markerWidth, style.urgency ? '22px' : '6px');
    assert.equal(style.markerHeight, style.urgency ? '6px' : '6px');
    assert.equal(style.markerRadius, style.urgency ? '1px' : '3px');
    // Squares encode urgency only, and never more than the three lifecycle steps.
    if (style.urgency) assert.ok(style.squares >= 1 && style.squares <= 3, `squares: ${style.squares}`);
    else assert.equal(style.squares, 0);
  }
  assert.equal(
    await page
      .locator('.summary-metrics dd')
      .first()
      .evaluate((element) => getComputedStyle(element).fontSize),
    '22px',
  );
  assert.equal(await page.locator('.operational-workspace .badge').count(), 0);
  const queue = page.getByRole('region', { name: 'Очередь рисков' });
  const temperature = queue.getByRole('row', { name: /Температура ВШ-3/ });
  assert.match(await temperature.innerText(), /46\s*%/);
  assert.match(await temperature.innerText(), /Критический/);
  assert.match(await queue.locator('tbody tr').first().innerText(), /82\s*%/);
  for (const [width, height] of [
    [1920, 1080],
    [1366, 768],
  ]) {
    await page.setViewportSize({ width, height });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    const right = await page.locator('.operational-side').boundingBox();
    const left = await page.locator('.sidebar').boundingBox();
    const table = await queue.boundingBox();
    // The side panel keeps a workable width without starving the queue of horizontal space.
    assert.ok(right.width >= 296 && right.x + right.width <= width, `side panel: ${right.width}`);
    assert.ok(table.x >= left.x + left.width);
    // "Тип" stays readable at every supported width instead of collapsing to "Состояние фа...".
    const typeColumn = await queue.locator('.queue-type').first().boundingBox();
    assert.ok(typeColumn && typeColumn.width >= 88, `type column: ${typeColumn?.width}`);
    const typeText = await queue.locator('td.queue-type').first().innerText();
    assert.doesNotMatch(typeText, /…|\.\.\./, `truncated type: ${typeText}`);
    // The queue itself must not need horizontal scrolling at supported widths.
    const queueScroll = await page
      .locator('.risk-queue .table-scroll')
      .evaluate((element) => element.scrollWidth - element.clientWidth);
    assert.equal(queueScroll, 0, `queue overflows by ${queueScroll}px at ${width}`);
    assert.equal(await queue.getByRole('columnheader', { name: 'Вероятность' }).isVisible(), true);
    assert.ok((await queue.locator('tbody tr').count()) >= 10);
    if (width === 1920) {
      const tenth = await queue.locator('tbody tr').nth(9).boundingBox();
      const coverage = await page.locator('.coverage-status').boundingBox();
      assert.ok(tenth.y + tenth.height < height && coverage.y + coverage.height < height);
    }
    await page.screenshot({ path: `test-results/overview-${width}.png` });
    if (width === 1920) await page.screenshot({ path: 'test-results/overview-semantic-1920.png' });
  }
  await page.getByRole('button', { name: '1–6 ч', exact: true }).click();
  await page.getByText('Показано 4 из 24 загруженных').waitFor();
  await page.getByLabel('Объект в очереди').selectOption('203');
  await page.getByText('Показано 1 из 24 загруженных').waitFor();
  await page.getByRole('searchbox').fill('ПК 88+50');
  await page.getByText('Показано 1 из 24 загруженных').waitFor();
  await temperature.focus();
  await page.keyboard.press('Enter');
  await page.waitForURL('**/predictions/OP-001');
  await page.getByRole('heading', { level: 1, name: 'Температура ВШ-3', exact: true }).waitFor();
  await page.goBack();
  await ready();
  await page
    .getByRole('region', { name: 'Состояние объектов' })
    .getByRole('link', { name: /объект Фита/ })
    .click();
  await page.waitForURL('**/objects/203');
  await page.getByRole('heading', { name: 'объект Фита', exact: true }).waitFor();
  await page.goBack();
  await ready();
  // Verify tab order through the main workflow, without mouse activation.
  await page
    .getByRole('navigation', { name: 'Основная навигация' })
    .getByRole('link', { name: 'Оперативный центр', exact: true })
    .focus();
  const visited = new Set();
  for (let index = 0; index < 65; index++) {
    await page.keyboard.press('Tab');
    const area = await page.evaluate(() =>
      document.activeElement?.closest('.queue-filters')
        ? 'filters'
        : document.activeElement?.matches('.queue-row')
          ? 'queue'
          : document.activeElement?.closest('.object-status-list')
            ? 'objects'
            : null,
    );
    if (area) visited.add(area);
    if (visited.has('objects')) break;
  }
  assert.deepEqual([...visited], ['filters', 'queue', 'objects']);
  await page.setViewportSize({ width: 1920, height: 1080 });
  await scenario('/predictions', 'loading');
  await queue.getByRole('status').filter({ hasText: 'Загрузка данных' }).waitFor();
  await page.getByText('80%', { exact: true }).waitFor();
  await page.screenshot({ path: 'test-results/overview-loading.png' });
  await ready();
  await scenario('/dashboard/summary', 'error');
  await page.getByRole('region', { name: 'Сводка инфраструктуры' }).getByRole('alert').waitFor();
  await page.getByText('Показано 24 из 24 загруженных').waitFor();
  await page.getByText('Показано объектов: 8').waitFor();
  await page.screenshot({ path: 'test-results/overview-summary-error.png' });
  await scenario('/predictions', 'error');
  await queue.getByRole('alert').waitFor();
  await page.getByText('80%', { exact: true }).waitFor();
  await page.screenshot({ path: 'test-results/overview-queue-error.png' });
  await page.evaluate(async () => {
    const workerUrl = performance
      .getEntriesByType('resource')
      .map((entry) => entry.name)
      .findLast((url) => new URL(url).pathname === '/src/api/mocks/browser.ts');
    const { worker } = await import(workerUrl);
    worker.resetHandlers();
  });
  await queue.getByRole('button', { name: 'Повторить' }).click();
  await ready();
  await scenario('/predictions', 'error', false);
  await page.getByRole('button', { name: 'Обновить очередь рисков' }).click();
  await queue.getByText('Показаны сохранённые данные. Требуется обновление.').waitFor();
  assert.equal(await queue.locator('tbody tr').count(), 24);
  await page.screenshot({ path: 'test-results/overview-stale.png' });
  await scenario('/predictions', 'empty');
  await queue.getByRole('heading', { name: 'Активных рисков нет' }).waitFor();
  assert.deepEqual(errors, []);
  console.log(
    'PASS: Operational Center 1920/1366, counts, urgency, 46% critical, filters, navigation, keyboard flow, independent loading/errors, retry, empty and cached stale data.',
  );
} catch (error) {
  await page.screenshot({ path: 'test-results/overview-check-failure.png' });
  throw error;
} finally {
  await browser.close();
}
