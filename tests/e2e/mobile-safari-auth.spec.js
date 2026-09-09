import {test,expect} from '@playwright/test';
import {loginAccount} from './account-helper.js';

test('mobile Safari retains and clears a first-party session',async({page,context,browserName})=>{
  test.skip(browserName!=='webkit','Mobile Safari compatibility coverage');
  const loginResponse=page.waitForResponse(response=>response.url().endsWith('/api/v1/auth/login'));
  await loginAccount(page,test.info().project.name);
  const response=await loginResponse;
  expect(response.status()).toBe(200);
  expect(response.headers()['set-cookie'].toLowerCase()).toContain('samesite=lax');
  await expect(page).toHaveURL(/\/app\/overview$/);
  const cookies=await context.cookies();
  expect(cookies.find(cookie=>cookie.name==='aiopt_session')).toMatchObject({httpOnly:true,path:'/'});
  expect((await context.request.get('/api/v1/auth/me')).status()).toBe(200);
  await page.reload();
  await expect(page).toHaveURL(/\/app\/overview$/);
  await expect(page.locator('h1')).toHaveText('Overview');
  await page.getByRole('button',{name:'Log out'}).click();
  await expect(page).toHaveURL(/\/$/);
  expect((await context.request.get('/api/v1/auth/me')).status()).toBe(401);
  expect((await context.cookies()).some(cookie=>cookie.name==='aiopt_session')).toBeFalsy();
});
