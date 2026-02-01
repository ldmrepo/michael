import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: '/webapp/',
  build: {
    outDir: '../../dist/webapp',
    emptyOutDir: true,
  },
  server: {
    port: 3001,
    host: true,
  },
});
