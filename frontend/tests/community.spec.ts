import { test, expect, type Page } from '@playwright/test';
import { SLOTS } from '../src/game/data';

async function post<T = any>(page: Page, path: string, body: unknown): Promise<T> {
  return page.evaluate(async ({ path, body }) => {
    const session = await (await fetch('/api/auth/me')).json();
    const response = await fetch('/api' + path, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Out-Request': '1', 'X-CSRF-Token': session.csrf ?? '' }, body: JSON.stringify(body) });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  }, { path, body });
}

test('locked trophies show requirements, keyboard details and sharing fallback on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/achievements');
  const card = page.getByRole('button', { name: 'First XI — locked. View achievement details', exact: true });
  await expect(card).toBeVisible();
  expect(await card.locator('.locked-trophy').evaluate(el => getComputedStyle(el).filter)).toBe('grayscale(1)');
  await card.focus(); await page.keyboard.press('Enter');
  const dialog = page.getByRole('dialog', { name: 'First XI', exact: true });
  await expect(dialog).toContainText('eleven drafted players');
  await expect(dialog.getByRole('progressbar')).toHaveAttribute('value', '0');
  await page.evaluate(() => { Object.defineProperty(navigator, 'share', { value: undefined, configurable: true }); Object.defineProperty(navigator, 'clipboard', { value: { writeText: async () => { throw new Error('Unavailable'); } }, configurable: true }); });
  await dialog.getByRole('button', { name: 'Share this challenge', exact: true }).click();
  await expect(dialog.getByLabel('Details to share')).toContainText('My next OUT. challenge: First XI');
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(card).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/trophy-cabinet-mobile.png', fullPage: true });
  const stamp = Date.now().toString();
  await post(page, '/auth/register', { username: `guest${stamp}`, email: `guest${stamp}@example.com`, password: 'save my cricket progress' });
  expect((await (await page.request.get('/api/progress')).json()).guest).toBe(false);
  const backup = await post<{code:string}>(page, '/auth/recovery-code', {});
  expect(backup.code).toHaveLength(32);
});

test('friends join a cup, earn colorful trophies, share a public card and keep the rematch together', async ({ browser, baseURL }) => {
  test.setTimeout(240000);
  const contexts = await Promise.all([0, 1].map(() => browser.newContext({ baseURL })));
  const [a, b] = await Promise.all(contexts.map(c => c.newPage()));
  const errors: string[] = [];
  try {
    const stamp = Date.now().toString();
    for (const [i, page] of [a, b].entries()) {
      page.on('pageerror', e => errors.push(e.message)); await page.goto('/');
      await post(page, '/auth/register', { username: `cup${i}${stamp}`, email: `cup${i}${stamp}@example.com`, password: 'a colorful cricket passphrase' });
    }
    await a.goto('/groups');
    await a.getByLabel('New group name').fill('The pavilion');
    await a.getByRole('button', { name: 'Create group', exact: true }).click();
    await expect(a.getByRole('heading', { name: 'The pavilion', exact: true })).toBeVisible();
    const id = new URL(a.url()).searchParams.get('id')!;
    const group = await (await a.request.get(`/api/groups/${id}`)).json();
    await b.goto(`/groups?invite=${group.invite}`);
    await b.getByRole('button', { name: 'Join this group', exact: true }).click();
    await expect(b.getByRole('heading', { name: 'The pavilion', exact: true })).toBeVisible();
    await a.reload();
    await a.getByRole('combobox', { name: 'Draft challenge', exact: true }).click();
    await a.getByRole('option', { name: /^IPL Under 85/ }).click();
    await a.getByRole('button', { name: 'Start cup · 2 players', exact: true }).click();
    await expect(a.getByRole('table', { name: 'Group cup standings' })).toBeVisible();
    await a.getByRole('button', { name: 'Play fixture', exact: true }).click();
    await expect(a.getByRole('heading', { name: 'Waiting room', exact: true })).toBeVisible();
    const roomId = await a.evaluate(() => sessionStorage.getItem('out-online-room'));
    let room = await (await a.request.get(`/api/rooms/${roomId}`)).json();
    await b.goto(`/rooms?code=${room.code}`);
    await expect(b.getByRole('heading', { name: 'Waiting room', exact: true })).toBeVisible();
    for (const page of [a, b]) await page.getByRole('button', { name: 'Ready', exact: true }).click();
    await expect(a.getByRole('button', { name: 'Start match', exact: true })).toBeEnabled();
    const started = a.waitForResponse(r => r.url().endsWith(`/rooms/${roomId}/actions`) && r.request().postDataJSON().action === 'start');
    await a.getByRole('button', { name: 'Start match', exact: true }).click();
    room = await (await started).json();
    while (room.state.phase === 'draft') {
      const page = room.state.turn === 0 ? a : b;
      if (!room.state.rolled) room = await post(page, `/rooms/${roomId}/actions`, { action: 'roll', version: room.version, draft_revision: room.state.draftRevision });
      expect(room.state.rolled.players.every((p: { rating: number }) => p.rating < 85)).toBe(true);
      const [player_id, slots] = Object.entries(room.state.rolled.allowedSlots)[0] as [string, string[]];
      room = await post(page, `/rooms/${roomId}/actions`, { action: 'pick', version: room.version, draft_revision: room.state.draftRevision, player_id, slot_id: slots[0] });
    }
    await expect(a.getByRole('link', { name: 'View trophies & saved results ↗', exact: true })).toBeVisible({ timeout: 70000 });
    const final = await (await a.request.get(`/api/rooms/${roomId}`)).json();
    const winner = final.state.champion === final.you ? a : b;
    await winner.getByRole('button', { name: 'Back to tournament', exact: true }).click();
    await a.getByRole('button', { name: 'Play again', exact: true }).click();
    await expect(b.getByRole('button', { name: /Your rematch is waiting/ })).toBeVisible();
    await b.getByRole('button', { name: /Your rematch is waiting/ }).click();
    await expect(b.getByRole('heading', { name: 'Waiting room', exact: true })).toBeVisible();
    expect(await a.evaluate(() => sessionStorage.getItem('out-online-room'))).toBe(await b.evaluate(() => sessionStorage.getItem('out-online-room')));
    await a.goto('/achievements');
    const trophy = a.getByRole('button', { name: 'Hidden gems — earned. View achievement details', exact: true });
    await expect(trophy).toBeVisible();
    await expect(trophy.locator('.locked-trophy')).toHaveCount(0);
    await a.screenshot({ path: 'test-results/trophy-cabinet-earned.png', fullPage: true });
    await trophy.click();
    const dialog = a.getByRole('dialog', { name: 'Hidden gems', exact: true });
    await a.evaluate(() => { Object.defineProperty(navigator, 'share', { configurable: true, value: async (data: ShareData) => { (window as any).shared = data; } }); });
    await dialog.getByRole('button', { name: 'Share achievement', exact: true }).click();
    await expect(dialog.getByRole('status')).toContainText('Shared.');
    const shared = await a.evaluate(() => (window as any).shared);
    expect(shared.text).toContain('Hidden gems'); expect(shared.url).toContain('/share/achievement/');
    const publicContext = await browser.newContext({ baseURL });
    const publicPage = await publicContext.newPage(); await publicPage.goto(shared.url);
    await expect(publicPage.getByRole('heading', { name: 'Hidden gems', exact: true })).toBeVisible();
    await expect(publicPage.getByText(`cup0${stamp}`, { exact: true })).toBeVisible();
    await publicContext.close();
    await a.goto(`/groups?id=${id}`);
    await expect(a.getByRole('table', { name: 'Group cup standings' })).toBeVisible();
    await a.screenshot({ path: 'test-results/group-cup-desktop.png', fullPage: true });
    expect(errors).toEqual([]);
  } finally { await Promise.all(contexts.map(c => c.close())); }
});

test('practice saves a viewed result and its trophies before leaving the result screen', async ({ page }) => {
  test.setTimeout(180000);
  await page.goto('/?practice=under-85');
  const created = page.waitForResponse(r => r.url().endsWith('/api/games') && r.request().method() === 'POST');
  await page.getByRole('button', { name: /Practice vs AI/ }).click();
  let saved = await (await created).json(); const id = saved.id;
  expect(saved.state.preset).toBe('under-85');
  await expect(page.getByRole('region', { name: 'Draft turn order' })).toContainText('Chance 1 of 2');
  for (let index = 0; index < 11; index++) {
    saved = await post(page, `/games/${id}/actions`, { action: 'roll', version: saved.version });
    const player = saved.state.rolled.players.find((p: any) => SLOTS.some(s => !saved.state.yourXI[s.id] && s.accepts.includes(p.role)));
    const slot = SLOTS.find(s => !saved.state.yourXI[s.id] && s.accepts.includes(player.role))!;
    saved = await post(page, `/games/${id}/actions`, { action: 'pick', version: saved.version, player_id: player.id, slot_id: slot.id });
    await expect.poll(async () => { saved = await (await page.request.get(`/api/games/${id}`)).json(); return saved.state.turn; }, { timeout: 25000, intervals: [1000] }).not.toBe('opp');
  }
  await page.reload();
  await page.getByRole('button', { name: 'Simulate match', exact: true }).click();
  await page.getByRole('button', { name: 'Skip to result', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Play again', exact: true })).toBeEnabled();
  await page.getByRole('link', { name: 'View your trophies & match history ↗', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Hidden gems — earned. View achievement details', exact: true })).toBeVisible();
  const progress = await (await page.request.get('/api/progress')).json();
  expect(progress.history).toHaveLength(1); expect(progress.stats.completed).toBe(1);
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Play again', exact: true })).toBeEnabled();
  expect((await (await page.request.get('/api/progress')).json()).history).toHaveLength(1);
});
