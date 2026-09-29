import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    // Разрешаем любые Host-заголовки: приложение проксируется через внешний
    // хост (например, live-preview песочницы вида *.e2b.app), и Vite 5 по
    // умолчанию блокирует незнакомые Host — без этого dev-сервер отдаёт 403.
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
});
