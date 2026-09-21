import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';

const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
const origin = process.env.TEST_BASE_URL || 'http://127.0.0.1:5173';
const errors = [];
await mkdir('test-results', { recursive: true });

const DRAFT = 'WO-2026-0917'; // draft linked to prediction HYDRO-003
const APPROVED = 'WO-2026-0918'; // approved, linked to OW-016
const COMPLETED = 'WO-2026-0901';
const REJECTED = 'WO-2026-0910';

// Each theme run starts from a fresh page, so the in-memory mock ticket store resets with it.
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
    const registry = page.getByRole('region', { name: 'Реестр нарядов' });

    await page.goto(`${origin}/tickets`);
    await page.getByRole('heading', { name: 'Наряды', exact: true }).waitFor();
    await page.getByText('15 нарядов').waitFor();
    assert.equal(await page.locator('html').getAttribute('data-theme'), theme);

    // Dense registry, restrained statuses, Moscow time despite the browser timezone.
    assert.equal(await registry.locator('tbody tr').count(), 15);
    assert.equal(await page.locator('.tickets-registry .badge.tone-critical').count(), 0);
    const statusStyle = await page
      .locator('.workflow-status')
      .first()
      .evaluate((element) => {
        const style = getComputedStyle(element);
        return { radius: style.borderRadius, border: style.borderTopWidth, size: style.fontSize };
      });
    assert.deepEqual(statusStyle, { radius: '4px', border: '1px', size: '12px' });
    assert.match(await registry.innerText(), /20\.09\.2026, \d{2}:\d{2} МСК/);
    // Pending work is listed before finished records.
    const firstRow = await registry.locator('tbody tr').first().innerText();
    assert.match(firstRow, /Черновик/);

    for (const [width, height] of [
      [1920, 1080],
      [1366, 768],
    ]) {
      await page.setViewportSize({ width, height });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      const table = await page.locator('.tickets-registry-panel .table-scroll').boundingBox();
      assert.ok(table.x + table.width <= width);
      assert.ok((await registry.locator('tbody tr').count()) >= 12);
      await page.screenshot({ path: `test-results/tickets-registry-${theme}-${width}.png` });
    }
    await page.setViewportSize({ width: 1920, height: 1080 });

    // Filters and search narrow the loaded dataset and report the real count.
    await page.getByLabel('Статус наряда').selectOption('completed');
    await page.getByText('4 из 15 нарядов').waitFor();
    await page.getByLabel('Статус наряда').selectOption('all');
    await page.getByRole('searchbox').fill('HYDRO-003');
    await page.getByText('1 из 15 нарядов').waitFor();
    await page.getByRole('searchbox').fill('');
    await page.getByText('15 нарядов').waitFor();

    // Detail drawer opens from a focused row with Enter and syncs the URL.
    const draftRow = registry.getByRole('row', { name: new RegExp(DRAFT) });
    await draftRow.focus();
    await page.keyboard.press('Enter');
    await page.waitForURL(new RegExp(`ticketId=${DRAFT}`));
    const drawer = page.getByRole('dialog');
    await drawer.getByText('Проверка дренажного насоса № 2').waitFor();
    assert.match(await drawer.innerText(), /HYDRO-003/);
    assert.match(await drawer.innerText(), /20\.09\.2026, \d{2}:\d{2} МСК/);
    if (theme === 'dark') await page.screenshot({ path: 'test-results/tickets-detail-drawer.png' });

    // Workflow C — draft → rejected through a confirmation dialog.
    await drawer.getByRole('button', { name: 'Отклонить' }).click();
    const rejectDialog = page.getByRole('dialog', { name: 'Отклонить наряд?' });
    await rejectDialog.waitFor();
    await rejectDialog.getByRole('button', { name: 'Отклонить' }).click();
    await page.getByText('Наряд отклонён. Дальнейшие действия недоступны.').waitFor();
    assert.equal(await page.getByRole('button', { name: 'Согласовать' }).count(), 0);
    await page.keyboard.press('Escape');
    await page.waitForURL((url) => !url.search.includes('ticketId'));

    // Workflow B — draft → approved → completed.
    await page.goto(`${origin}/tickets?ticketId=${APPROVED}`);
    await page.getByRole('dialog').getByText('Согласован').waitFor();
    if (theme === 'dark') await page.screenshot({ path: 'test-results/tickets-approved.png' });
    await page.getByRole('button', { name: 'Отметить выполненным' }).click();
    const completeDialog = page.getByRole('dialog', { name: 'Отметить наряд выполненным?' });
    await completeDialog.waitFor();
    assert.match(await completeDialog.innerText(), /После завершения статус нельзя изменить в интерфейсе\./);
    await completeDialog.getByRole('button', { name: 'Отметить выполненным' }).click();
    await page.getByText('Наряд выполнен. Дальнейшие действия недоступны.').waitFor();
    assert.match(await page.getByRole('dialog').innerText(), /Завершён/);
    if (theme === 'dark') await page.screenshot({ path: 'test-results/tickets-completed.png' });
    await page.keyboard.press('Escape');

    // Terminal statuses expose no lifecycle actions at all.
    for (const id of [COMPLETED, REJECTED]) {
      await page.goto(`${origin}/tickets?ticketId=${id}`);
      await page.getByText(/Дальнейшие действия недоступны/).waitFor();
      assert.equal(await page.getByRole('button', { name: 'Согласовать' }).count(), 0);
      assert.equal(await page.getByRole('button', { name: 'Отметить выполненным' }).count(), 0);
    }

    // Deep link to an unknown ticket stays local to the drawer.
    await page.goto(`${origin}/tickets?ticketId=WO-NOPE`);
    await page.getByText('Наряд не найден').waitFor();
    await page.getByText('15 нарядов').waitFor();

    // Workflow A — investigation hands the prediction over, the ticket is created and linked back.
    await page.goto(`${origin}/predictions/OW-004`);
    await page.getByRole('heading', { level: 1, name: 'Температура ВШ-3' }).waitFor();
    await page.getByRole('link', { name: /Создать наряд/ }).click();
    await page.waitForURL(/\/tickets\?predictionId=OW-004$/);
    const createDrawer = page.getByRole('dialog');
    await createDrawer.waitFor();
    await page.waitForFunction(() => document.querySelector('.ticket-form input.input')?.value?.length > 0);
    assert.equal(
      await page.getByLabel('Название').inputValue(),
      'Проверка: Температура ВШ-3',
      'title must be prefilled from the prediction',
    );
    const description = await page.getByLabel('Описание').inputValue();
    assert.match(description, /Калибровка измерительного тракта или замена термопары\./);
    assert.match(await createDrawer.innerText(), /ИСТОЧНИК/);
    assert.match(await createDrawer.innerText(), /Критический/);
    if (theme === 'dark') await page.screenshot({ path: 'test-results/tickets-create-drawer.png' });

    await page.getByLabel('Исполнитель').selectOption('Смена А');
    await page.getByRole('button', { name: 'Создать черновик' }).click();
    // The create drawer is replaced by the detail drawer of the new ticket.
    await page.waitForURL((url) => url.searchParams.has('ticketId') && !url.searchParams.has('predictionId'));
    const createdId = new URL(page.url()).searchParams.get('ticketId');
    const createdDrawer = page.locator('.ticket-detail');
    await createdDrawer.waitFor();
    assert.equal(await page.locator('.ticket-detail .workflow-status').innerText(), 'Черновик');
    assert.match(await createdDrawer.innerText(), /Проверка: Температура ВШ-3/);
    assert.match(await createdDrawer.innerText(), /Смена А/);
    await page.getByText('16 нарядов').waitFor();

    // The prediction now reports the existing work order instead of offering creation again.
    await page.getByRole('link', { name: 'Открыть прогноз' }).click();
    await page.waitForURL('**/predictions/OW-004');
    await page.getByTestId('existing-ticket').waitFor();
    assert.match(await page.getByTestId('existing-ticket').innerText(), new RegExp(createdId));
    assert.equal(await page.getByRole('link', { name: /Создать наряд/ }).count(), 0);

    // A prediction that already owns a ticket cannot get a second one. HYDRO-003 is a fixture,
    // so this holds across reloads, unlike the ticket created above in the session-scoped store.
    await page.goto(`${origin}/tickets?predictionId=HYDRO-003`);
    const duplicate = page.getByTestId('duplicate-ticket');
    await duplicate.waitFor();
    assert.match(await duplicate.innerText(), new RegExp(DRAFT));
    assert.equal(await page.getByLabel('Название').count(), 0, 'create form must stay hidden');
    await duplicate.getByRole('button', { name: 'Открыть наряд' }).click();
    await page.waitForURL(new RegExp(`ticketId=${DRAFT}`));
    await page.locator('.ticket-detail').waitFor();

    await page.close();
  }
  assert.deepEqual(errors, []);
  console.log(
    'PASS Tickets: dark/light registry at 1920 and 1366, filters and search, detail drawer deep link, workflow A create-from-prediction with link-back, workflow B approve then complete, workflow C reject, terminal statuses without actions, unknown ticket and duplicate protection.',
  );
} finally {
  await browser.close();
}
