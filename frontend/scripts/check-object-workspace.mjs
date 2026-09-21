import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';

const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
const origin = process.env.TEST_BASE_URL || 'http://127.0.0.1:5173';
const errors = [];
await mkdir('test-results', { recursive: true });

// ПК0–ПК14+50 and ПК48–ПК80 from the object Фита topology fixture.
const FIRST_RANGE = 14.5;
const FOURTH_RANGE = 32;
const CRITICAL_SEGMENT = /Участок ПК 88\+50 — ПК 112/;

const moduleUrl = (page, pathname) =>
  page.evaluate(
    (name) =>
      performance
        .getEntriesByType('resource')
        .map((entry) => entry.name)
        .findLast((url) => new URL(url).pathname === name),
    pathname,
  );

const navigate = async (page, label) => {
  await page
    .getByRole('navigation', { name: 'Основная навигация' })
    .getByRole('link', { name: label, exact: true })
    .click();
  await page.getByRole('heading', { name: label, exact: true }).waitFor();
};

// Stay inside the SPA so MSW overrides survive a reload, and remount the page so the
// cleared cache is refetched through the override.
async function scenario(page, endpoint, state) {
  await navigate(page, 'Аналитика');
  await page.evaluate(
    async ({ endpoint, state, worker, provider }) => {
      // Import the loaded module URLs so overrides target the app's own instances.
      const [{ worker: instance }, { queryClient }, { setObjectWorkspaceScenario }] = await Promise.all([
        import(worker),
        import(provider),
        import('/src/api/mocks/scenarios.ts'),
      ]);
      instance.resetHandlers();
      setObjectWorkspaceScenario(instance, endpoint, state, 203);
      queryClient.clear();
    },
    {
      endpoint,
      state,
      worker: await moduleUrl(page, '/src/api/mocks/browser.ts'),
      provider: await moduleUrl(page, '/src/app/providers/AppProviders.tsx'),
    },
  );
  await navigate(page, 'Оперативный центр');
  await page
    .getByRole('region', { name: 'Состояние объектов' })
    .getByRole('link', { name: /объект Фита/ })
    .click();
  await page.waitForURL('**/objects/203');
}

async function ready(page) {
  await page.getByRole('heading', { name: 'объект Фита', exact: true }).waitFor();
  await page.getByText('Показано 24 из 24 загруженных').waitFor();
  await page.getByRole('button', { name: CRITICAL_SEGMENT }).waitFor();
}

try {
  for (const theme of ['dark', 'light']) {
    const page = await browser.newPage({
      colorScheme: theme,
      viewport: { width: 1920, height: 1080 },
      locale: 'ru-RU',
      timezoneId: 'America/Los_Angeles',
    });
    page.setDefaultTimeout(12_000);
    page.on('pageerror', (error) => errors.push(`${theme}: ${error.message}`));
    await page.goto(`${origin}/objects/203`);
    await ready(page);
    assert.equal(await page.locator('html').getAttribute('data-theme'), theme);

    // Object detail comes from GET /objects/:id, in Moscow time despite the browser timezone.
    assert.match(
      await page.locator('.page-header').innerText(),
      /Инженерный объект · 860 каналов · ML-покрытие 84%/,
    );
    assert.match(await page.locator('.object-header-meta').innerText(), /20\.09\.2026, 18:42 МСК/);
    const summary = page.getByRole('region', { name: 'Состояние объекта' });
    assert.match(await summary.innerText(), /Критический/);
    assert.match(await summary.innerText(), /722 \/ 860 каналов/);

    // No filled risk pills and no decorative surfaces anywhere on the workspace.
    assert.equal(await page.locator('.object-workspace .badge').count(), 0);
    const indicators = await page.locator('.object-workspace .semantic-indicator').evaluateAll((list) =>
      list.map((element) => {
        const style = getComputedStyle(element);
        return { background: style.backgroundColor, border: style.borderTopWidth, size: style.fontSize };
      }),
    );
    assert.ok(indicators.length > 0);
    for (const style of indicators)
      assert.deepEqual(style, { background: 'rgba(0, 0, 0, 0)', border: '0px', size: '12px' });

    // Proportional geometry: visual length follows piket_to - piket_from.
    const widths = await page
      .locator('.topology-segment-line')
      .evaluateAll((list) => list.map((element) => element.getBoundingClientRect().width));
    assert.equal(widths.length, 20);
    assert.ok(Math.abs(widths[3] / widths[0] - FOURTH_RANGE / FIRST_RANGE) < 0.02);
    const critical = page.getByRole('button', { name: CRITICAL_SEGMENT });
    const neutral = page.getByRole('button', { name: /Участок ПК 0 — ПК 14\+50/ });
    const fill = (locator) =>
      locator.locator('.topology-segment-line').evaluate((el) => getComputedStyle(el).fill);
    assert.notEqual(await fill(critical), await fill(neutral));
    assert.match(await fill(neutral), /^rgb\(/);

    // Tooltip: enterprise content, readable in both themes.
    await critical.hover();
    const tooltip = page.getByRole('tooltip');
    await tooltip.waitFor();
    assert.match(await tooltip.innerText(), /ПК 88\+50 — ПК 112/);
    assert.match(await tooltip.innerText(), /Критический/);
    assert.match(await tooltip.innerText(), /82\s*%/);
    assert.equal(await tooltip.evaluate((el) => getComputedStyle(el).boxShadow), 'none');
    await page.mouse.move(0, 0);
    await page.keyboard.press('Escape');
    await tooltip.waitFor({ state: 'hidden' });

    // Segment captions must not overlap each other at any supported width.
    const captions = await page
      .locator('.topology-segment-label text')
      .evaluateAll((list) => list.map((element) => element.getBoundingClientRect()));
    for (const [index, box] of captions.entries())
      if (index > 0) assert.ok(box.left >= captions[index - 1].right, `caption ${index} overlaps`);

    for (const [width, height] of [
      [1920, 1080],
      [1366, 768],
    ]) {
      await page.setViewportSize({ width, height });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      const table = await page.locator('.object-predictions .table-scroll').boundingBox();
      assert.ok(table.x + table.width <= width);
      assert.equal(await page.getByRole('columnheader', { name: 'Вероятность' }).first().isVisible(), true);
      assert.ok((await page.locator('.object-predictions tbody tr').count()) >= 8);
      if (width === 1920) {
        // First viewport shows header, summary, topology and at least eight rows.
        const eighth = await page.locator('.object-predictions tbody tr').nth(7).boundingBox();
        assert.ok(eighth.y + eighth.height < height, `eighth row at ${eighth.y}`);
      }
      await page.screenshot({ path: `test-results/object-workspace-${theme}-${width}.png` });
    }
    await page.setViewportSize({ width: 1920, height: 1080 });

    // Mouse selection filters the table by the numeric piket range of the segment.
    await critical.click();
    assert.equal(await critical.getAttribute('aria-pressed'), 'true');
    await page
      .getByText('Выбран участок: ПК 88+50 — ПК 112 · Вентшахта ВШ-3 · 4 прогноза', { exact: true })
      .waitFor();
    await page.getByText('Показано 4 из 24 загруженных').waitFor();
    assert.equal(await page.locator('.object-predictions tbody tr').count(), 4);
    if (theme === 'dark')
      await page.screenshot({ path: 'test-results/object-workspace-selected-critical.png' });
    await page.getByRole('button', { name: 'Сбросить', exact: true }).click();
    await page.getByText('Показано 24 из 24 загруженных').waitFor();

    // Keyboard: segments are reachable by Tab, show a visible focus ring and act on Enter.
    await page.getByRole('button', { name: 'Обновить топологию', exact: true }).focus();
    let focusedSegment = null;
    for (let index = 0; index < 8 && focusedSegment === null; index++) {
      await page.keyboard.press('Tab');
      focusedSegment = await page.evaluate(() =>
        document.activeElement?.classList.contains('topology-segment')
          ? document.activeElement.getAttribute('aria-label')
          : null,
      );
    }
    assert.ok(focusedSegment, 'a topology segment must be reachable with Tab');
    const ring = await page.evaluate(
      () => getComputedStyle(document.activeElement.querySelector('.topology-segment-ring')).stroke,
    );
    assert.match(ring, /^rgb\(/);
    assert.notEqual(ring, 'none');
    await page.keyboard.press('Enter');
    await page.getByText('Выбран участок:', { exact: false }).waitFor();
    await page.keyboard.press(' ');
    await page.getByText('Показано 24 из 24 загруженных').waitFor();

    // Row navigation into the Prediction Investigation shell.
    const row = page.getByRole('row', { name: /Температура ВШ-3/ });
    await row.focus();
    await page.keyboard.press('Enter');
    await page.waitForURL('**/predictions/OW-004');
    await page.getByRole('heading', { name: 'Прогноз OW-004', exact: true }).waitFor();
    await page.goBack();
    await ready(page);

    if (theme === 'dark') {
      // Independent failures: topology fails, detail and predictions keep working.
      await scenario(page, 'topology', 'error');
      await page.getByRole('region', { name: 'Топология объекта' }).getByRole('alert').waitFor();
      await page.getByText('Показано 24 из 24 загруженных').waitFor();
      await page.getByRole('heading', { name: 'объект Фита', exact: true }).waitFor();
      await page.screenshot({ path: 'test-results/object-workspace-topology-error.png' });

      await scenario(page, 'predictions', 'error');
      await page.getByRole('region', { name: 'Прогнозы объекта' }).getByRole('alert').waitFor();
      await page.getByRole('button', { name: CRITICAL_SEGMENT }).waitFor();

      await scenario(page, 'topology', 'empty');
      await page.getByText('Топология объекта недоступна').waitFor();
      await page.getByText('Показано 24 из 24 загруженных').waitFor();

      await scenario(page, 'predictions', 'empty');
      await page.getByText('Активных прогнозов для объекта нет').waitFor();
      await page.getByRole('button', { name: CRITICAL_SEGMENT }).waitFor();

      await page.evaluate(
        async (worker) => {
          const { worker: instance } = await import(worker);
          instance.resetHandlers();
        },
        await moduleUrl(page, '/src/api/mocks/browser.ts'),
      );

      // An unknown object id resolves to the dedicated not-found state.
      await page.goto(`${origin}/objects/9999`);
      await page.getByRole('heading', { name: 'Объект не найден' }).waitFor();
      await page.getByRole('link', { name: 'К списку объектов' }).click();
      await page.waitForURL('**/objects');
    }
    await page.close();
  }
  assert.deepEqual(errors, []);
  console.log(
    'PASS: Object Workspace dark/light at 1920 and 1366, proportional SVG topology, tooltip, mouse and keyboard selection, numeric piket filtering, row navigation, independent errors, empty states and object 404.',
  );
} finally {
  await browser.close();
}
