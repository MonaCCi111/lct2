import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';

const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
const origin = process.env.TEST_BASE_URL || 'http://127.0.0.1:5173';
const errors = [];
await mkdir('test-results', { recursive: true });

const TEMP = 'OW-004'; // 46% ANALOG_TEMP, critical, numeric telemetry
const POWER = 'OW-005'; // state telemetry with chatter and a failure
const DOOR = 'DOOR-006'; // unsupported ML, telemetry still available
const TICKETED = 'HYDRO-003'; // prediction that already has a work order
const NO_TELEMETRY = 'OW-001'; // known channel without stored telemetry

const summaryText = (page) => page.getByTestId('telemetry-summary').innerText();
const moduleUrl = (page, pathname) =>
  page.evaluate(
    (name) =>
      performance
        .getEntriesByType('resource')
        .map((entry) => entry.name)
        .findLast((url) => new URL(url).pathname === name),
    pathname,
  );

try {
  for (const theme of ['dark', 'light']) {
    const page = await browser.newPage({
      colorScheme: theme,
      viewport: { width: 1920, height: 1080 },
      locale: 'ru-RU',
      timezoneId: 'America/Los_Angeles',
    });
    page.setDefaultTimeout(15_000);
    page.on('pageerror', (error) => errors.push(`${theme}: ${error.message}`));

    await page.goto(`${origin}/predictions/${TEMP}`);
    await page.getByRole('heading', { level: 1, name: 'Температура ВШ-3' }).waitFor();
    assert.equal(await page.locator('html').getAttribute('data-theme'), theme);

    // Prediction context: ready ML values, Moscow time despite the browser timezone.
    const context = page.getByRole('complementary', { name: 'Оценка прогноза' });
    assert.match(await context.innerText(), /Критический/);
    assert.match(await context.innerText(), /46\s*%/);
    assert.match(await context.innerText(), /Требуется проверка в течение 1–6 часов/);
    assert.match(await context.innerText(), /54/);
    assert.match(await page.locator('.investigation-header-meta').innerText(), /20\.09\.2026, 18:38 МСК/);
    assert.doesNotMatch(await page.locator('.prediction-investigation').innerText(), /Отказ произойдёт/);

    // Restrained semantics: no filled risk pills anywhere on the screen.
    assert.equal(await page.locator('.prediction-investigation .badge.tone-critical').count(), 0);
    const indicators = await page
      .locator('.prediction-investigation .semantic-indicator')
      .evaluateAll((list) =>
        list.map((element) => {
          const style = getComputedStyle(element);
          return { background: style.backgroundColor, border: style.borderTopWidth };
        }),
      );
    assert.ok(indicators.length > 0);
    for (const style of indicators)
      assert.deepEqual(style, { background: 'rgba(0, 0, 0, 0)', border: '0px' });

    // Numeric telemetry renders a real line, not a marketing surface.
    await page.locator('.telemetry-chart svg path.recharts-line-curve').first().waitFor();
    const stroke = await page
      .locator('.telemetry-chart path.recharts-line-curve')
      .first()
      .evaluate((element) => ({
        fill: getComputedStyle(element).fill,
        width: getComputedStyle(element).strokeWidth,
      }));
    assert.equal(stroke.fill, 'none', 'telemetry line must not be area-filled');
    assert.match(await summaryText(page), /Минимум .+ °C/);
    assert.match(await summaryText(page), /144 точек/);

    // Alarm markers exist and stay small; the chart is not flooded with colour.
    assert.ok((await page.locator('.telemetry-marker-alarm').count()) > 0, 'expected alarm markers');
    assert.ok((await page.locator('.telemetry-events li').count()) > 0, 'expected an event list');

    // Chart tooltip shows the Moscow timestamp and the measured value.
    const chartBox = await page.locator('.telemetry-chart').boundingBox();
    await page.mouse.move(chartBox.x + chartBox.width * 0.4, chartBox.y + chartBox.height * 0.5);
    const tooltip = page.locator('.telemetry-tooltip');
    await tooltip.waitFor();
    assert.match(await tooltip.innerText(), /\d{2}\.\d{2}\.\d{4}, \d{2}:\d{2} МСК/);
    assert.match(await tooltip.innerText(), /°C/);
    await page.mouse.move(0, 0);

    for (const [width, height] of [
      [1920, 1080],
      [1366, 768],
    ]) {
      await page.setViewportSize({ width, height });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      const chart = await page.locator('.telemetry-chart').boundingBox();
      assert.ok(chart.width > 380, `chart too narrow at ${width}: ${chart.width}`);
      assert.ok(chart.x + chart.width <= width);
      if (width === 1920) {
        // First viewport must carry the whole decision: risk, chart, factors, recommendation, CTA.
        const cta = await page.locator('.investigation-cta').boundingBox();
        assert.ok(cta.y + cta.height < height, `CTA below the fold: ${cta.y}`);
        assert.ok((await page.locator('.risk-factors li').count()) >= 2);
      }
      await page.screenshot({ path: `test-results/prediction-investigation-${theme}-${width}.png` });
    }
    await page.setViewportSize({ width: 1920, height: 1080 });

    // Range control: keyboard reachable, switches the loaded window.
    await page.getByRole('button', { name: '6 ч', exact: true }).focus();
    await page.keyboard.press('Enter');
    await page.getByText('96', { exact: true }).waitFor();
    await page.getByRole('button', { name: '48 ч', exact: true }).click();
    await page.getByText('192', { exact: true }).waitFor();
    await page.getByRole('button', { name: '24 ч', exact: true }).click();
    await page.getByText('144', { exact: true }).waitFor();

    // Technical details stay collapsed and open from the keyboard.
    const details = page.locator('details.investigation-technical');
    assert.equal(await details.evaluate((element) => element.open), false);
    await page.locator('details.investigation-technical > summary').focus();
    await page.keyboard.press('Enter');
    await page.waitForFunction(
      () => document.querySelector('details.investigation-technical')?.open === true,
    );
    assert.match(await details.innerText(), /ANALOG_TEMP/);

    // State telemetry: a step chart with real state names on the axis.
    await page.goto(`${origin}/predictions/${POWER}`);
    await page.getByRole('heading', { level: 1, name: 'Фаза B · тяговый ввод' }).waitFor();
    await page.locator('.telemetry-chart svg path.recharts-line-curve').first().waitFor();
    assert.match(await summaryText(page), /Телеметрия состояний/);
    // SVG tick labels carry no innerText, so read their text content instead.
    const axis = await page.locator('.recharts-cartesian-axis-tick-value').allTextContents();
    for (const state of ['Норма', 'Просадка', 'Отказ'])
      assert.ok(axis.includes(state), `state axis must label "${state}": ${axis.join('|')}`);
    assert.ok((await page.locator('.telemetry-marker-chatter').count()) > 0, 'expected chatter markers');
    const events = await page.locator('.telemetry-events').innerText();
    assert.match(events, /Дребезг сигнала/);
    assert.match(events, /Аварийное значение/);
    if (theme === 'dark')
      await page.screenshot({ path: 'test-results/prediction-investigation-state-telemetry.png' });

    // Unsupported ML: no invented low/1%/ITS 99, telemetry still available.
    await page.goto(`${origin}/predictions/${DOOR}`);
    await page.getByRole('heading', { level: 1, name: 'Дверь технического помещения' }).waitFor();
    const unsupported = page.getByTestId('ml-unsupported');
    await unsupported.waitFor();
    assert.match(await unsupported.innerText(), /ML-анализ недоступен/);
    const unsupportedContext = await page.getByRole('complementary', { name: 'Оценка прогноза' }).innerText();
    assert.doesNotMatch(unsupportedContext, /Низкий/);
    assert.doesNotMatch(unsupportedContext, /\b1\s*%/);
    assert.doesNotMatch(unsupportedContext, /\b99\b/);
    await page.locator('.telemetry-chart svg').first().waitFor();
    assert.match(await summaryText(page), /Телеметрия состояний/);
    if (theme === 'dark')
      await page.screenshot({ path: 'test-results/prediction-investigation-unsupported.png' });

    // Existing work order replaces the create action.
    await page.goto(`${origin}/predictions/${TICKETED}`);
    await page.getByRole('heading', { level: 1, name: 'Дренажный насос № 2' }).waitFor();
    assert.equal(await page.getByRole('link', { name: /Создать наряд/ }).count(), 0);
    assert.match(await page.getByTestId('existing-ticket').innerText(), /WO-2026-0917/);

    // Empty telemetry keeps the prediction intact.
    await page.goto(`${origin}/predictions/${NO_TELEMETRY}`);
    await page.getByText('Телеметрия отсутствует').waitFor();
    assert.match(
      await page.getByRole('complementary', { name: 'Оценка прогноза' }).innerText(),
      /Вероятность отказа/,
    );
    if (theme === 'dark')
      await page.screenshot({ path: 'test-results/prediction-investigation-no-telemetry.png' });

    // Telemetry failure is local: the prediction context survives it. MSW owns the response, so
    // the override goes through the worker and the page is remounted inside the SPA.
    await page.goto(`${origin}/predictions/${TEMP}`);
    await page.getByRole('heading', { level: 1, name: 'Температура ВШ-3' }).waitFor();
    await page.getByRole('link', { name: 'Прогнозы', exact: true }).first().click();
    await page.waitForURL('**/predictions');
    await page.getByRole('heading', { name: 'Прогнозы', exact: true }).waitFor();
    // Wait for real rows: skeleton placeholders are rows too, but they are not clickable.
    await page.locator('tr.predictions-registry-row').first().waitFor();
    await page.evaluate(
      async (worker) => {
        const [{ worker: instance }, { setTelemetryScenario }] = await Promise.all([
          import(worker),
          import('/src/api/mocks/scenarios.ts'),
        ]);
        instance.resetHandlers();
        setTelemetryScenario(instance, 'error');
      },
      await moduleUrl(page, '/src/api/mocks/browser.ts'),
    );
    // Open a prediction whose telemetry has not been cached yet, so the failure is the first load.
    await page.locator('tr.predictions-registry-row').first().click();
    await page.waitForURL(/\/predictions\/[A-Z]+-\d+/);
    await page.getByText('Не удалось загрузить телеметрию. Данные прогноза остаются доступны.').waitFor();
    assert.match(
      await page.getByRole('complementary', { name: 'Оценка прогноза' }).innerText(),
      /Вероятность отказа/,
    );
    assert.equal(await page.getByRole('button', { name: 'Повторить' }).count(), 1);
    if (theme === 'dark')
      await page.screenshot({ path: 'test-results/prediction-investigation-telemetry-error.png' });
    await page.reload();

    // Handoff to the tickets flow carries the prediction and creates nothing.
    await page.goto(`${origin}/predictions/${TEMP}`);
    const cta = page.getByRole('link', { name: /Создать наряд/ });
    await cta.waitFor();
    await cta.click();
    await page.waitForURL(new RegExp(`/tickets\\?predictionId=${TEMP}$`));
    // The tickets page opens its create flow for this prediction. The page heading itself is
    // aria-hidden while the modal drawer is open, so the drawer is what we assert on.
    const handoff = page.getByRole('dialog');
    await handoff.waitFor();
    assert.match(await handoff.innerText(), /Создание наряда/);
    assert.match(await handoff.innerText(), new RegExp(TEMP));
    // Nothing is created by the handoff itself: the draft still has to be submitted.
    assert.equal(await page.getByRole('button', { name: 'Создать черновик' }).count(), 1);

    await page.close();
  }
  assert.deepEqual(errors, []);
  console.log(
    'PASS Prediction Investigation: dark/light at 1920 and 1366, numeric and step telemetry, alarm/chatter markers, Moscow tooltips, 6/24/48h ranges, keyboard range and disclosure, unsupported ML, empty telemetry, local telemetry error, existing ticket and tickets handoff.',
  );
} finally {
  await browser.close();
}
