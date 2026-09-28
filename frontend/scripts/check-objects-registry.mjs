import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { spawn } from 'node:child_process';

// Dedicated port keeps this check isolated from the other agent's running app.
const origin = process.env.TEST_BASE_URL || 'http://127.0.0.1:5182';
const server = process.env.TEST_BASE_URL
  ? null
  : spawn(
      process.execPath,
      ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5182', '--strictPort'],
      { stdio: 'pipe', windowsHide: true, env: { ...process.env, VITE_ENABLE_MOCKS: 'true' } },
    );
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
const errors = [];
try {
  if (server)
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Registry Vite did not start')), 15000);
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
    await page.goto(`${origin}/objects`);
    const ready = () => page.getByText('Показано 8 из 8 загруженных объектов').waitFor();
    await ready();
    assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
    assert.equal(await page.locator('.objects-registry-row').count(), 8);
    const first = page.locator('.objects-registry-row').first();
    // Objects display their Greek letter; the Russian name stays in the cell's title.
    assert.match(await first.innerText(), /объект θ/);
    assert.equal(await first.locator('.objects-registry-name').getAttribute('title'), 'объект Фита');
    assert.match(await first.innerText(), /Критический/);
    assert.match(await first.innerText(), /84%/);
    assert.match(await first.innerText(), /722 \/ 860/);
    assert.match(await first.innerText(), /20.09.2026, 18:42 МСК/);
    for (const [width, height] of [
      [1920, 1080],
      [1366, 768],
    ]) {
      await page.setViewportSize({ width, height });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      assert.ok(
        await page
          .locator('.objects-registry .table-scroll')
          .evaluate((el) => el.scrollWidth <= el.clientWidth),
        'Columns fit at desktop widths',
      );
      const styles = await page.locator('.objects-registry-row').evaluateAll((rows) =>
        rows.map((row) => ({
          height: row.getBoundingClientRect().height,
          font: getComputedStyle(row.cells[0]).fontSize,
          background: getComputedStyle(row.querySelector('.risk-indicator')).backgroundColor,
          label: row.querySelector('.risk-indicator').textContent,
        })),
      );
      assert.ok(
        styles.every(
          (style) =>
            style.height <= 42 &&
            style.font === '13px' &&
            style.background === 'rgba(0, 0, 0, 0)' &&
            style.label.trim(),
        ),
      );
      const filterBoxes = await page
        .locator(
          '.objects-registry-filters input, .objects-registry-filters select, .objects-registry-filters button',
        )
        .evaluateAll((controls) =>
          controls.map((el) => {
            const box = el.getBoundingClientRect();
            return { right: box.right, bottom: box.bottom };
          }),
        );
      assert.ok(filterBoxes.every((box) => box.right <= width && box.bottom <= height));
      await page.screenshot({ path: `test-results/objects-${theme}-${width}.png` });
    }
    const search = page.getByRole('searchbox', { name: 'Поиск объектов' });
    await search.fill('  фИТа ');
    await page.getByText('Показано 1 из 8 загруженных объектов').waitFor();
    await page.getByLabel('Состояние', { exact: true }).selectOption('high');
    await page.getByText('Объекты не найдены', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Сбросить фильтры', exact: true }).click();
    await ready();
    await page.getByLabel('Состояние', { exact: true }).selectOption('high');
    await page.getByText('Показано 2 из 8 загруженных объектов').waitFor();
    await page.getByRole('button', { name: 'Сбросить фильтры', exact: true }).click();
    await ready();
    // Sequential keyboard flow: search -> select -> first row (reset is disabled).
    await search.focus();
    await page.keyboard.press('Tab');
    assert.equal(
      await page.getByLabel('Состояние', { exact: true }).evaluate((el) => document.activeElement === el),
      true,
    );
    await page.keyboard.press('Tab');
    assert.equal(await first.evaluate((el) => document.activeElement === el), true);
    assert.equal(await first.evaluate((el) => getComputedStyle(el).outlineStyle), 'solid');
    const expectedId = '203';
    await page.keyboard.press('Enter');
    await page.waitForURL(`**/objects/${expectedId}`);
    await page.goBack();
    await ready();
    await first.click();
    await page.waitForURL(`**/objects/${expectedId}`);
    await page.close();
  }
  assert.deepEqual(errors, []);
  console.log(
    'PASS Objects Registry: dark/light 1920/1366, dense table, no overflow, aggregate risk/coverage, Moscow time, search/filter/reset, keyboard focus and click/Enter navigation.',
  );
} finally {
  await browser.close();
  server?.kill();
}
