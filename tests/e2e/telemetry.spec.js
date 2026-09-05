import {test,expect} from '@playwright/test';
const password='BrowserTestPassword123';
async function register(page,username){
  await page.goto('/register');await page.getByLabel('Display Name').fill(username);await page.getByLabel('Username').fill(username);await page.getByLabel('Email').fill(`${username}@example.com`);await page.locator('input[name="password"]').fill(password);await page.getByLabel('Confirm Password').fill(password);await page.getByRole('button',{name:'Create Profile'}).click();await expect(page).toHaveURL(/\/login$/);await page.getByLabel('Username or Email').fill(username);await page.locator('input[name="password"]').fill(password);await page.getByRole('button',{name:'Sign In'}).click();await expect(page).toHaveURL(/\/app\/overview$/);
}
test('register, import, analytics, isolation, and logout',async({page})=>{
  const suffix=Date.now(),first=`browserA${suffix}`,second=`browserB${suffix}`;await register(page,first);await page.getByRole('link',{name:'Import Data'}).click();
  await page.getByLabel('Choose telemetry file').setInputFiles({name:'sample.csv',mimeType:'text/csv',buffer:Buffer.from('timestamp,application,provider,model,input_tokens,output_tokens,cost,latency_ms\n2026-01-01T00:00:00Z,Assistant,openai,gpt-5,12,3,0.01,120\n')});await page.getByRole('button',{name:'Analyze File'}).click();await expect(page.getByText(/Detected 1 rows/)).toBeVisible();await page.getByRole('button',{name:'Import telemetry'}).click();await expect(page).toHaveURL(/\/app\/overview$/);await expect(page.getByText('15',{exact:true})).toBeVisible();
  for(const item of ['Usage','Costs','Models']){await page.getByRole('link',{name:item,exact:true}).click();await expect(page.locator('h1')).toHaveText(item)}
  await page.getByRole('button',{name:'Log out'}).click();await expect(page).toHaveURL(/\/$/);await register(page,second);await expect(page.getByText('No telemetry imported yet')).toBeVisible();await page.getByRole('button',{name:'Log out'}).click();
});
for(const [name,width,height] of [['1920x1080',1920,1080],['1600x900',1600,900],['1366x768',1366,768],['1024x768',1024,768]])test(`layout ${name}`,async({page})=>{await page.setViewportSize({width,height});await page.goto('/');await expect(page.locator('h1')).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth)).toBeTruthy()});
