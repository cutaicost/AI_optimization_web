import {defineConfig,devices} from '@playwright/test';
const python=process.platform==='win32'?'.venv\\Scripts\\python.exe':'/venv/bin/python';
export default defineConfig({
  testDir:'tests/e2e',timeout:65*60*1000,fullyParallel:false,workers:1,
  projects:[
    {name:'desktop-chromium',use:{browserName:'chromium'}},
    {name:'mobile-safari',use:{...devices['iPhone 13'],browserName:'webkit'}},
    {name:'desktop-webkit',testMatch:'webkit-desktop.spec.js',use:{browserName:'webkit',viewport:{width:1366,height:768}}},
  ],
  use:{baseURL:'http://127.0.0.1:3000',trace:'retain-on-failure'},
  webServer:[
    {command:`${python} -m uvicorn apps.api.aiopt_web.main:app --host 127.0.0.1 --port 8000`,url:'http://127.0.0.1:8000/api/v1/health',reuseExistingServer:false,timeout:30000,env:{...process.env,EMBEDDED_IMPORT_WORKER:'true',MODEL_REFRESH_ENABLED:'false'}},
    {command:'npm run dev:web',url:'http://127.0.0.1:3000',reuseExistingServer:false,timeout:30000},
  ],
});
