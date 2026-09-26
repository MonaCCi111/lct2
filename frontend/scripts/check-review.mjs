import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium } from 'playwright';

const origin = process.env.TEST_BASE_URL || 'http://127.0.0.1:5173';
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
const errors = [];
await mkdir('test-results', { recursive: true });

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
    await page.goto(`${origin}/review`);
    const table = page.getByRole('table', { name: 'Исторические черновики для проверки' });
    await table.getByText('Прогноз модели', { exact: true }).waitFor();
    assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
    assert.equal(await table.locator('tbody tr').count(), 2);
    assert.equal(await table.getByText('Наблюдаемое событие', { exact: true }).count(), 1);
    assert.equal(await table.getByText('0.985', { exact: true }).count(), 1);
    assert.doesNotMatch(await table.innerText(), /0\.985\s*%/);
    assert.doesNotMatch(await table.locator('thead').innerText(), /Риск|Срочность|Вероятность отказа|ИТС/);
    assert.match(await table.innerText(), /2025-12-10T09:00:00/);
    assert.match(await page.getByLabel('Режим данных').innerText(), /Исторические данные/);
    assert.match(await page.getByLabel('Режим данных').innerText(), /2026-06-30T23:59:59/);
    assert.doesNotMatch(await page.getByLabel('Режим данных').innerText(), /МСК|UTC|live/i);
    assert.equal(
      await page
        .getByRole('navigation', { name: 'Основная навигация' })
        .getByRole('link', { name: 'Очередь проверки', exact: true })
        .count(),
      1,
    );

    for (const [width, height] of [
      [1920, 1080],
      [1366, 768],
    ]) {
      await page.setViewportSize({ width, height });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.screenshot({ path: `test-results/review-${theme}-${width}.png`, fullPage: true });
    }

    if (theme === 'dark') {
      const forecastRow = table.getByRole('row', { name: /канал 178259/ });
      await forecastRow.focus();
      await forecastRow.press('Enter');
      await page.waitForURL('**/review/*');
      await page.getByRole('heading', { name: 'Черновик проверки' }).waitFor();
      assert.match(await page.locator('.review-detail-page').innerText(), /ИТС не рассчитан/);
      assert.match(
        await page.locator('.review-detail-page').innerText(),
        /model_score_is_not_physical_failure_probability/,
      );
      const evidence = page.getByRole('table', { name: 'Свидетельства черновика' });
      await evidence.getByText('Есть питание', { exact: true }).waitFor();
      assert.match(await evidence.innerText(), /2025-12-10T08:16:53/);
      assert.match(await evidence.innerText(), /Нет/);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.screenshot({ path: 'test-results/review-detail-dark-1366.png', fullPage: true });
    }
    await page.close();
  }
  assert.deepEqual(errors, []);
  console.log(
    'PASS Review: v2 drafts, decimal score semantics, literal historical time, filters, keyboard detail navigation, evidence, dark/light and 1920/1366.',
  );
} finally {
  await browser.close();
}
