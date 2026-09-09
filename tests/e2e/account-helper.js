import {expect} from '@playwright/test';

export const password='BrowserTestPassword123';

const runId=`${Date.now()}${Math.floor(Math.random()*1e6)}`;
const accounts=new Map();
const registered=new Set();

function account(projectName,slot){
  const key=`${projectName}:${slot}`;
  if(!accounts.has(key)){
    const projectCode=projectName==='mobile-safari'?'ms':'dc';
    const slotCode=slot==='secondary'?'s':'p';
    const username=`browser${projectCode}${slotCode}${runId}`;
    accounts.set(key,{display_name:username,username,email:`${username}@example.com`,password,confirm_password:password});
  }
  return accounts.get(key);
}

async function registerWithRateLimit(request,page,data){
  const deadline=Date.now()+65*60*1000;
  for(;;){
    const response=await request.post('/api/v1/auth/register',{data});
    if(response.status()!==429){
      expect(response.ok(),await response.text()).toBeTruthy();
      return;
    }
    if(Date.now()>=deadline)throw new Error('Registration remained rate limited after 65 minutes');
    const retryAfter=Number(response.headers()['retry-after']);
    const waitMs=Number.isFinite(retryAfter)&&retryAfter>0?retryAfter*1000:60*1000;
    await page.waitForTimeout(Math.min(waitMs,deadline-Date.now()));
  }
}

export async function loginAccount(page,projectName,slot='primary'){
  const data=account(projectName,slot);
  const key=`${projectName}:${slot}`;
  if(!registered.has(key)){
    await registerWithRateLimit(page.request,page,data);
    registered.add(key);
  }
  await page.goto('/login');
  await page.getByLabel('Username or Email').fill(data.username);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole('button',{name:'Log In'}).click();
  await expect(page).toHaveURL(/\/app\/overview$/);
  return data;
}

export async function clickWithRateLimit(page,buttonName,path){
  const deadline=Date.now()+65*60*1000;
  for(;;){
    const responsePromise=page.waitForResponse(response=>new URL(response.url()).pathname===path&&response.request().method()==='POST');
    await page.getByRole('button',{name:buttonName}).click();
    const response=await responsePromise;
    if(response.status()!==429){expect(response.ok(),await response.text()).toBeTruthy();return;}
    if(Date.now()>=deadline)throw new Error(`${path} remained rate limited after 65 minutes`);
    const retryAfter=Number(response.headers()['retry-after']);
    await page.waitForTimeout(Number.isFinite(retryAfter)&&retryAfter>0?retryAfter*1000:60*1000);
  }
}
