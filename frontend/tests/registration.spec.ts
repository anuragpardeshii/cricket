import { test, expect } from '@playwright/test';

test('registration accepts seven characters and rejects six', async ({ page }) => {
  const suffix = Date.now().toString();
  await page.goto('/register');
  await page.getByLabel('Username', { exact: true }).fill(`pw${suffix}`);
  await page.getByLabel('Email address', { exact: true }).fill(`pw${suffix}@example.com`);
  await page.getByLabel('Phone number', { exact: true }).fill(suffix.slice(-10));
  await page.getByLabel('Password', { exact: true }).fill('Abc12!');
  await expect(page.locator('#password-feedback')).toContainText('Use at least 7 characters.');
  await expect(page.getByLabel('Password', { exact: true })).toHaveAttribute('aria-invalid', 'true');
  await page.getByLabel('Password', { exact: true }).fill('Abc123!');
  await expect(page.locator('#password-feedback')).toContainText('Length requirement met.');
  await expect(page.locator('#password-feedback')).toContainText('7/7');
  await page.getByLabel('Confirm password', { exact: true }).fill('Abc123!');
  await page.getByRole('button', { name: 'Register', exact: true }).click();
  await expect(page.getByText('Account created', { exact: true })).toBeVisible();
});
