import {defineConfig} from 'vite';
export default defineConfig({root:'apps/web',base:'/',build:{outDir:'../../dist',emptyOutDir:true},server:{proxy:{'/api':'http://127.0.0.1:8000'}}});
