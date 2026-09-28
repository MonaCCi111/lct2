import { chromium } from 'playwright';

const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, locale: 'ru-RU' });
  const failures = [];
  page.on('pageerror', (error) => failures.push(error.message));
  page.on('response', (response) => {
    if (response.url().includes('/api/v2/') && response.status() >= 400) failures.push(`${response.status()} ${response.url()}`);
  });
  await page.goto('http://127.0.0.1:5173/replay');
  await page.getByRole('button', { name: 'Построить таймлайн' }).click();
  await page.locator('option[value^="custom_"]').waitFor({ state: 'attached', timeout: 90000 });
  await page.getByRole('slider', { name: 'Ползунок исторического таймлайна' }).fill('100');
  await page.locator('.dispatch-replay-clock small').filter({ hasText: 'шаг 100' }).waitFor();
  const text = await page.locator('body').innerText();
  if (!text.includes('Выбранный объект и период') || !text.includes('шаг 100')) failures.push('Произвольный период не открылся на шаге 100');
  console.log(JSON.stringify({ failures, customScenarioVisible: text.includes('Выбранный объект и период'), step100: text.includes('шаг 100') }));
  if (failures.length) process.exitCode = 1;
} finally {
  await browser.close();
}
