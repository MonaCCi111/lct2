import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { spawn } from 'node:child_process';

const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
const origin = process.env.TEST_BASE_URL || 'http://127.0.0.1:5173';
await mkdir('test-results', { recursive: true });
const errors = [];
const preview = spawn(
  process.execPath,
  ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', '4175', '--strictPort'],
  { stdio: 'pipe', windowsHide: true },
);
try {
  for (const theme of ['dark', 'light']) {
    const page = await browser.newPage({
      colorScheme: theme,
      viewport: { width: 1920, height: 1080 },
      locale: 'ru-RU',
    });
    page.on('pageerror', (error) => errors.push(error.message));
    await page.goto(`${origin}/overview`);
    await page.getByText('Показано 24 из 24 загруженных').waitFor();
    assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
    assert.equal(await page.locator('html').evaluate((el) => getComputedStyle(el).colorScheme), theme);
    // Check text, focus and marker contrast against both canvas and raised surface.
    const contrast = await page.evaluate(() => {
      const css = getComputedStyle(document.documentElement);
      const rgb = (name) =>
        css
          .getPropertyValue(name)
          .trim()
          .slice(1)
          .match(/../g)
          .map((v) => parseInt(v, 16) / 255);
      const lum = (name) =>
        rgb(name)
          .map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
          .reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0);
      const ratio = (a, b) => (Math.max(lum(a), lum(b)) + 0.05) / (Math.min(lum(a), lum(b)) + 0.05);
      return ['--bg-app', '--bg-surface', '--bg-surface-elevated'].flatMap((bg) =>
        [
          '--text-primary',
          '--text-secondary',
          '--text-muted',
          '--risk-critical',
          '--risk-high',
          '--risk-medium',
          '--risk-low',
          '--focus',
        ].map((token) => ({ token, ratio: ratio(token, bg) })),
      );
    });
    for (const item of contrast)
      assert.ok(item.ratio >= (item.token === '--focus' ? 3 : 4.5), `${theme} ${item.token}: ${item.ratio}`);
    assert.equal(
      await page
        .locator('.semantic-indicator')
        .first()
        .evaluate((el) => getComputedStyle(el).backgroundColor),
      'rgba(0, 0, 0, 0)',
    );
    const row = page.getByRole('row', { name: /Температура ВШ-3/ });
    assert.match(await row.innerText(), /46\s*%/);
    assert.match(await row.innerText(), /Критический/);
    for (const [width, height] of [
      [1920, 1080],
      [1366, 768],
    ]) {
      await page.setViewportSize({ width, height });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      const side = await page.locator('.operational-side').boundingBox();
      assert.ok(side.width >= 310 && side.x + side.width <= width);
      await page.screenshot({ path: `test-results/overview-${theme}-${width}.png` });
    }
    await page.getByRole('button', { name: '1–6 ч', exact: true }).click();
    await page.getByText('Показано 4 из 24 загруженных').waitFor();
    await page.getByRole('button', { name: 'Профиль', exact: true }).click();
    const select = page.getByLabel('Тема интерфейса');
    assert.equal(await select.inputValue(), 'system');
    await select.selectOption(theme);
    assert.equal(await page.evaluate(() => localStorage.getItem('dolos-theme')), theme);
    await page.emulateMedia({ colorScheme: theme === 'dark' ? 'light' : 'dark' });
    assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
    await page.reload();
    await page.getByText('Показано 24 из 24 загруженных').waitFor();
    assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
    await page.getByRole('button', { name: 'Профиль', exact: true }).click();
    await page.getByLabel('Тема интерфейса').selectOption('system');
    await page.waitForFunction(
      (expected) => document.documentElement.dataset.theme === expected,
      theme === 'dark' ? 'light' : 'dark',
    );
    await page.emulateMedia({ colorScheme: theme });
    await page.waitForFunction((expected) => document.documentElement.dataset.theme === expected, theme);
    await page.keyboard.press('Escape');
    await page.goto(`${origin}/foundation`);
    await page.getByText('ML-анализ недоступен', { exact: true }).waitFor();
    await page.getByRole('tab', { name: 'Компоненты', exact: true }).click();
    assert.equal(await page.getByRole('button', { name: 'Недоступно', exact: true }).isDisabled(), true);
    const secondary = page.getByRole('button', { name: 'Вторичное', exact: true });
    const initialBackground = await secondary.evaluate((el) => getComputedStyle(el).backgroundColor);
    await secondary.hover();
    await page.waitForFunction(
      (initial) =>
        getComputedStyle(
          [...document.querySelectorAll('button')].find((el) => el.textContent === 'Вторичное'),
        ).backgroundColor !== initial,
      initialBackground,
    );
    await page.getByRole('button', { name: 'Открыть параметры', exact: true }).hover();
    await page.getByRole('tooltip', { name: 'Открыть параметры', exact: true }).waitFor();
    await page.keyboard.press('Escape');
    await page.getByLabel('Название объекта').focus();
    assert.equal(
      await page.getByLabel('Название объекта').evaluate((el) => getComputedStyle(el).outlineStyle),
      'solid',
    );
    await page.getByRole('button', { name: 'Открыть пример меню' }).click();
    await page.getByRole('menuitem', { name: 'Открыть панель' }).click();
    await page.getByRole('dialog').waitFor();
    await page.keyboard.press('Escape');
    for (const state of ['loading', 'empty', 'error', 'stale']) {
      await page.getByLabel('Состояние', { exact: true }).selectOption(state);
      if (state === 'loading')
        assert.equal(
          await page
            .locator('.skeleton')
            .first()
            .evaluate((el) => getComputedStyle(el).animationName),
          'none',
        );
      await page.screenshot({ path: `test-results/components-${theme}-${state}.png` });
    }
    await page.close();
  }
  // Production HTML must already have the correct theme while the app bundle is blocked.
  for (let attempt = 0; attempt < 50; attempt++) {
    try {
      if ((await fetch('http://127.0.0.1:4175')).ok) break;
    } catch {
      /* preview starting */
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  for (const preference of ['light', 'dark', 'system', 'corrupt']) {
    const page = await browser.newPage({ colorScheme: 'dark' });
    await page.addInitScript((value) => localStorage.setItem('dolos-theme', value), preference);
    await page.route('**/assets/*.js', (route) => route.abort());
    await page.goto('http://127.0.0.1:4175/overview');
    const expected = preference === 'light' ? 'light' : 'dark';
    assert.equal(await page.locator('html').getAttribute('data-theme'), expected);
    assert.equal(await page.locator('html').evaluate((el) => getComputedStyle(el).colorScheme), expected);
    assert.equal(
      await page.locator('html').evaluate((el) => getComputedStyle(el).backgroundColor),
      expected === 'dark' ? 'rgb(24, 25, 29)' : 'rgb(244, 245, 246)',
    );
    assert.equal(await page.locator('#root').innerHTML(), '');
    await page.close();
  }
  assert.deepEqual(errors, []);
  console.log(
    'Theme checks passed: both palettes, contrast, profile/persistence/OS changes, components, four overview screenshots, production pre-paint.',
  );
} finally {
  await browser.close();
  preview.kill();
}
