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

      const decisionPanel = page.getByRole('region', { name: 'Решение диспетчера' });
      await decisionPanel.getByRole('button', { name: 'Одобрить', exact: true }).click();
      await decisionPanel.getByRole('button', { name: 'Сохранить решение' }).click();
      await decisionPanel.getByText('Укажите причину решения диспетчера.', { exact: true }).waitFor();
      await decisionPanel.getByLabel('Причина решения').fill('Сигнал и контекст проверены диспетчером.');
      await decisionPanel.getByRole('button', { name: 'Сохранить решение' }).click();
      await decisionPanel.getByText('Решение сохранено', { exact: true }).waitFor();
      assert.equal(await decisionPanel.getByText('Наряд не создан.', { exact: true }).count(), 1);
      assert.equal(await decisionPanel.getByRole('button', { name: 'Одобрить', exact: true }).count(), 0);
      assert.match(
        await page.getByRole('table', { name: 'История решений по черновику' }).innerText(),
        /Сигнал и контекст проверены диспетчером\./,
      );

      const conflict = await page.evaluate(async () => {
        const response = await fetch(
          'http://localhost:8000/api/v2/drafts/power_phase_scada_v2%3A178259%3A20251210T090000/decisions',
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              decision: 'rejected',
              reason: 'Повторная попытка',
              idempotency_key: 'browser-conflict-attempt',
            }),
          },
        );
        return { status: response.status, body: await response.json() };
      });
      assert.equal(conflict.status, 409);
      assert.match(conflict.body.message, /уже сохранено решение/);

      await page.getByRole('link', { name: 'К очереди проверки' }).click();
      await page.waitForURL('**/review');
      const updatedTable = page.getByRole('table', { name: 'Исторические черновики для проверки' });
      const approvedRow = updatedTable.getByRole('row', { name: /канал 178259/ });
      await approvedRow.getByText('Одобрено', { exact: true }).waitFor();

      const observedRow = updatedTable.getByRole('row', { name: /канал 229590/ });
      await observedRow.click();
      await page.waitForURL('**/review/*');
      const rejectPanel = page.getByRole('region', { name: 'Решение диспетчера' });
      await rejectPanel.getByRole('button', { name: 'Отклонить', exact: true }).click();
      await rejectPanel.getByRole('button', { name: 'Сохранить решение' }).click();
      await rejectPanel.getByText('Укажите причину решения диспетчера.', { exact: true }).waitFor();
      await rejectPanel.getByLabel('Причина решения').fill('Событие не подтверждается доступным контекстом.');
      await rejectPanel.getByRole('button', { name: 'Сохранить решение' }).click();
      await rejectPanel.getByText('Решение сохранено', { exact: true }).waitFor();
      assert.match(
        await page.getByRole('table', { name: 'История решений по черновику' }).innerText(),
        /Событие не подтверждается доступным контекстом\./,
      );
      assert.equal(await rejectPanel.getByRole('button', { name: 'Отклонить', exact: true }).count(), 0);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.screenshot({ path: 'test-results/review-detail-dark-1366.png', fullPage: true });
    } else {
      const staleRow = table.getByRole('row', { name: /канал 178259/ });
      await staleRow.click();
      await page.getByRole('heading', { name: 'Черновик проверки' }).waitFor();
      const seeded = await page.evaluate(async () => {
        const response = await fetch(
          'http://localhost:8000/api/v2/drafts/power_phase_scada_v2%3A178259%3A20251210T090000/decisions',
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              decision: 'approved',
              reason: 'Решение из другой сессии',
              idempotency_key: 'browser-concurrent-attempt',
            }),
          },
        );
        return response.status;
      });
      assert.equal(seeded, 201);
      const stalePanel = page.getByRole('region', { name: 'Решение диспетчера' });
      await stalePanel.getByRole('button', { name: 'Отклонить', exact: true }).click();
      await stalePanel.getByLabel('Причина решения').fill('Конфликтующая попытка');
      await stalePanel.getByRole('button', { name: 'Сохранить решение' }).click();
      await stalePanel.getByText('По этому черновику уже сохранено решение.', { exact: true }).waitFor();
      assert.equal(await stalePanel.getByRole('button', { name: 'Отклонить', exact: true }).count(), 0);
    }
    await page.close();
  }
  assert.deepEqual(errors, []);
  console.log(
    'PASS Review: v2 drafts, approve/reject, required reason, 409 conflict, history, no automatic work order, evidence, dark/light and 1920/1366.',
  );
} finally {
  await browser.close();
}
