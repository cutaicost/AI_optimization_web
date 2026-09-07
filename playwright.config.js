import {defineConfig,devices} from '@playwright/test';
export default defineConfig({
  testDir:'tests/e2e',timeout:60000,fullyParallel:false,
  projects:[
    {name:'desktop-chromium',use:{browserName:'chromium'}},
    {name:'mobile-safari',use:{...devices['iPhone 13'],browserName:'webkit'}},
  ],
  use:{baseURL:'http://127.0.0.1:3000',trace:'retain-on-failure'},
  webServer:[
    {command:'.venv\\Scripts\\python.exe -m uvicorn apps.api.aiopt_web.main:app --host 127.0.0.1 --port 8000',url:'http://127.0.0.1:8000/api/v1/health',reuseExistingServer:false,timeout:30000,env:{...process.env,EMBEDDED_IMPORT_WORKER:'true'}},
    {command:'npm run dev:web',url:'http://127.0.0.1:3000',reuseExistingServer:false,timeout:30000},
  ],
});
