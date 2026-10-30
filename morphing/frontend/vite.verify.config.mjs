// Временный конфиг только для проверки панели в браузере: 3100 + API на 8123.
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: { host: '127.0.0.1', port: 3100, strictPort: true,
    proxy: { '/api': { target: 'http://127.0.0.1:8123', changeOrigin: true } } },
});
