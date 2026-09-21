import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { spawn } from 'node:child_process';

const origin = process.env.TEST_BASE_URL || 'http://127.0.0.1:5183';
const server = process.env.TEST_BASE_URL
  ? null
  : spawn(
      process.execPath,
      ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5183', '--strictPort'],
      { stdio: 'pipe', windowsHide: true, env: { ...process.env, VITE_ENABLE_MOCKS: 'true' } },
    );
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
const errors = [];
try {
  if (server)
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Predictions Vite did not start')), 15000);
      server.stdout.on('data', (chunk) => {
        if (chunk.toString().includes('Local:')) {
          clearTimeout(timer);
          resolve();
        }
      });
      server.once('exit', (code) => {
        clearTimeout(timer);
        reject(new Error(`Vite exited ${code}`));
      });
    });
  await mkdir('test-results', { recursive: true });
  for (const theme of ['dark', 'light']) {
    const page = await browser.newPage({
      colorScheme: theme,
      locale: 'ru-RU',
      timezoneId: 'Asia/Tokyo',
      viewport: { width: 1920, height: 1080 },
    });
    page.on('pageerror', (error) => errors.push(error.message));
    await page.goto(`${origin}/predictions`);
    const ready = () => page.getByText('Показано 24 из 24 загруженных прогнозов').waitFor();
    await ready();
    assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
    const temperature = page.getByRole('row', { name: /Температура ВШ-3/ });
    assert.match(await temperature.innerText(), /46\s*%/);
    assert.match(await temperature.innerText(), /Критический/);
    assert.match(await temperature.innerText(), /1–6 ч/);
    assert.equal(await temperature.locator('time').getAttribute('title'), '20.09.2026, 18:40 МСК');
    for (const [width, height] of [
      [1920, 1080],
      [1366, 768],
    ]) {
      await page.setViewportSize({ width, height });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      assert.ok(
        await page
          .locator('.predictions-registry .table-scroll')
          .evaluate((el) => el.scrollWidth <= el.clientWidth),
      );
      const styles = await page.locator('.predictions-registry-row').evaluateAll((rows) =>
        rows.map((row) => ({
          height: row.getBoundingClientRect().height,
          font: getComputedStyle(row.cells[0]).fontSize,
          indicators: [...row.querySelectorAll('.semantic-indicator')].map((el) => ({
            background: getComputedStyle(el).backgroundColor,
            label: el.textContent.trim(),
          })),
        })),
      );
      assert.ok(
        styles.every(
          (style) =>
            style.height <= 42 &&
            style.font === '13px' &&
            style.indicators.every((item) => item.background === 'rgba(0, 0, 0, 0)' && item.label),
        ),
      );
      for (const column of ['Срочность', 'Риск', 'Объект', 'Датчик', 'Вероятность'])
        assert.ok(await page.getByRole('columnheader', { name: column, exact: true }).isVisible());
      assert.ok(
        await page
          .getByRole('group', { name: 'Фильтры прогнозов' })
          .evaluate((el) => el.getBoundingClientRect().right <= innerWidth),
      );
      if (width === 1920) {
        const fifteenth = await page.locator('.predictions-registry-row').nth(14).boundingBox();
        const scroll = await page.locator('.predictions-registry .table-scroll').boundingBox();
        assert.ok(fifteenth.y + fifteenth.height <= Math.min(scroll.y + scroll.height, height));
      }
      await page.screenshot({ path: `test-results/predictions-${theme}-${width}.png` });
    }
    await page.getByRole('combobox', { name: 'Риск', exact: true }).selectOption('critical');
    await page.getByRole('combobox', { name: 'Срочность', exact: true }).selectOption('FLASH_1_6H');
    await page.getByRole('combobox', { name: 'Объект', exact: true }).selectOption('203');
    await page.getByRole('searchbox').fill('  ТеМп ');
    await page.getByText('Показано 1 из 24 загруженных прогнозов').waitFor();
    await temperature.focus();
    assert.equal(await temperature.evaluate((el) => getComputedStyle(el).outlineStyle), 'solid');
    await page.keyboard.press('Enter');
    await page.waitForURL('**/predictions/OP-001');
    await page.getByRole('heading', { level: 1, name: 'Температура ВШ-3', exact: true }).waitFor();
    await page.goBack();
    await ready();
    await temperature.click();
    await page.waitForURL('**/predictions/OP-001');
    await page.getByRole('heading', { level: 1, name: 'Температура ВШ-3', exact: true }).waitFor();
    await page.goBack();
    await ready();
    // Sequential tab order through all four filters.
    await page.getByRole('searchbox').focus();
    for (const label of ['Срочность', 'Риск', 'Объект']) {
      await page.keyboard.press('Tab');
      assert.equal(
        await page
          .getByRole('combobox', { name: label, exact: true })
          .evaluate((el) => document.activeElement === el),
        true,
      );
    }
    await page.getByRole('searchbox').fill('Нет такого датчика');
    await page.getByText('По заданным условиям прогнозы не найдены').waitFor();
    await page.getByRole('button', { name: 'Сбросить фильтры', exact: true }).click();
    await ready();
    for (const column of ['Вероятность', 'Объект', 'Обновлено']) {
      await page.getByRole('button', { name: column, exact: true }).click();
      assert.equal(
        await page.getByRole('columnheader', { name: column, exact: true }).getAttribute('aria-sort'),
        'ascending',
      );
      await page.getByRole('button', { name: column, exact: true }).click();
      assert.equal(
        await page.getByRole('columnheader', { name: column, exact: true }).getAttribute('aria-sort'),
        'descending',
      );
      await page.getByRole('button', { name: 'Вернуть порядок по срочности' }).click();
    }
    assert.match(await page.locator('.predictions-registry-row').first().innerText(), /82\s*%/);
    await page.evaluate(async () => {
      const resources = performance.getEntriesByType('resource').map((entry) => entry.name);
      const { worker } = await import(
        resources.findLast((url) => new URL(url).pathname === '/src/api/mocks/browser.ts')
      );
      const { setDashboardScenario } = await import('/src/api/mocks/scenarios.ts');
      setDashboardScenario(worker, '/predictions', 'error');
    });
    await page.getByRole('button', { name: 'Обновить прогнозы' }).click();
    await page.getByText('Показаны сохранённые данные. Требуется обновление.').waitFor();
    assert.equal(await page.locator('.predictions-registry-row').count(), 24);
    await page.evaluate(async () => {
      const resources = performance.getEntriesByType('resource').map((entry) => entry.name);
      const { worker } = await import(
        resources.findLast((url) => new URL(url).pathname === '/src/api/mocks/browser.ts')
      );
      worker.resetHandlers();
    });
    await page.getByRole('button', { name: 'Обновить', exact: true }).click();
    await page.getByText('Показаны сохранённые данные. Требуется обновление.').waitFor({ state: 'hidden' });
    await page.close();
  }
  assert.deepEqual(errors, []);
  console.log(
    'PASS Predictions Registry: dark/light 1920/1366, 15+ visible rows at 1920, no overflow, 46% critical, combined filters/reset, sorting, Moscow time, click/Enter/keyboard, stale recovery.',
  );
} finally {
  await browser.close();
  server?.kill();
}
