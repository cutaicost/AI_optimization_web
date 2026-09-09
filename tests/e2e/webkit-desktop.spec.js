import {test,expect} from '@playwright/test';

test('WebKit renders a realistic large desktop viewport',async({page},testInfo)=>{
  test.skip(testInfo.project.name!=='desktop-webkit','Dedicated desktop WebKit coverage');
  await page.goto('/');
  await expect(page.locator('h1')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth)).toBeTruthy();
});
