import { test, expect } from '@playwright/test';

test('admin analytics failure keeps access and offers a working retry', async ({ page }) => {
  await page.route('**/api/auth/me', route => route.fulfill({ json: { user: { id: 'admin', username: 'admin', is_admin: true }, csrf: 'test', guest: false } }));
  let attempts = 0;
  await page.route('**/api/admin/analytics?*', route => {
    attempts++;
    return attempts === 1
      ? route.fulfill({ status: 503, json: { detail: 'Service unavailable' } })
      : route.fulfill({ json: { totalRegistered: 2, newRegistrations: 1, activePlayers: 2, sessions: 3, draftStarts: 1, matchesFinished: 0, rooms: 0, liveRooms: 0, trend: [], devices: [], audience: [], popular: [], accounts: { guests: 1, administrators: 1, blocked: 0 }, activity: { practiceGames: 1, onlineRooms: 0, guestSessions: 1, registeredSessions: 2, events: [{ action: 'session.started', count: 3 }] } } });
  });
  await page.route('**/api/admin/users?*', route => route.fulfill({ json: { users: [], total: 0, page: 1, page_size: 10 } }));
  await page.goto('/dashboard');
  await expect(page.getByRole('alert')).toHaveText('Service unavailable');
  await expect(page.getByText('Your administrator access is confirmed', { exact: false })).toBeVisible();
  await expect(page.getByText('Sign in with an administrator account')).toHaveCount(0);
  await page.getByRole('button', { name: 'Retry analytics' }).click();
  await expect(page.getByRole('heading', { name: 'Account overview' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Play and sessions' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Most frequent activity' })).toBeVisible();
  expect(attempts).toBe(2);
});
