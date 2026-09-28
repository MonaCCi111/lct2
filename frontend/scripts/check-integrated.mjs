import { chromium } from 'playwright';

const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
const paths = process.env.CHECK_PATHS?.split(',') ?? ['/overview', '/objects', '/channels', '/situations', '/review', '/analytics', '/fire-history', '/replay'];
const port = process.env.CHECK_PORT || '5173';
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, locale: 'ru-RU' });
  const failures = [];
  page.on('pageerror', (error) => failures.push(error.message));
  page.on('response', (response) => {
    if (response.url().includes('/api/v2/') && response.status() >= 400) {
      failures.push(`${response.status()} ${response.url()}`);
    }
  });
  for (const path of paths) {
    await page.goto(`http://127.0.0.1:${port}${path}`, { waitUntil: 'domcontentloaded' });
    await page.locator('h1').first().waitFor({ timeout: 30000 });
    await page.waitForTimeout(700);
    if (path === '/replay') {
      try {
        await page.getByRole('slider', { name: 'Ползунок исторического таймлайна' }).waitFor({ timeout: 15000 });
      } catch (error) {
        console.log(`REPLAY_BODY ${(await page.locator('body').innerText()).slice(-1800)}`);
        console.log(`REPLAY_FAILURES ${JSON.stringify(failures)}`);
        throw error;
      }
      await page.getByRole('slider', { name: 'Ползунок исторического таймлайна' }).fill('100');
      if (!(await page.locator('body').innerText()).includes('шаг 100')) failures.push('Replay slider did not move to step 100');
    }
    const heading = await page.locator('h1').first().innerText();
    const text = await page.locator('body').innerText();
    console.log(`${path} | ${heading} | ${text.slice(-130).replaceAll('\n', ' ')}`);
    if (path === '/overview' || path === '/replay' || path === '/fire-history') {
      await page.screenshot({ path: `test-results/integrated-${path.slice(1)}.png`, fullPage: true });
    }
  }
  if (!process.env.CHECK_PATHS) {
    const details = [
      '/channels/2866',
      '/situations/GAS_NUMERIC%3A5578%3A20250407T100000',
      '/review/groups/review_v2%3A3388%3A20240701T012957',
      '/review/observed%3AOBSERVED_PUMP_FLOODED_STATUS%3A3388%3A20240701T012957',
    ];
    for (const path of details) {
      await page.goto(`http://127.0.0.1:${port}${path}`, { waitUntil: 'domcontentloaded' });
      await page.locator('h1').first().waitFor({ timeout: 30000 });
      await page.waitForTimeout(600);
      console.log(`${path} | ${await page.locator('h1').first().innerText()}`);
    }
  }
  console.log(`FAILURES ${JSON.stringify(failures)}`);
  if (failures.length) process.exitCode = 1;
} finally {
  await browser.close();
}
