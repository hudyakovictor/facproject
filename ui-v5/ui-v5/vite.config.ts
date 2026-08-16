import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 4175,
    allowedHosts: true,
    proxy: {
      "/api": {
        target: process.env.DEEPUTIN_API_URL || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    target: "es2022",
    sourcemap: true,
    rolldownOptions: {
      output: {
        /**
         * Разделение вендорного кода.
         *
         * Экраны уже загружаются лениво через `React.lazy`, но библиотеки
         * оставались в одном стартовом чанке. Разнесение по группам позволяет
         * браузеру кешировать их независимо: обновление кода приложения не
         * инвалидирует React и роутер.
         */
        advancedChunks: {
          groups: [
            { name: "vendor-react", test: /node_modules\/(react|react-dom|scheduler)\// },
            { name: "vendor-router", test: /node_modules\/@tanstack\// },
            { name: "vendor-radix", test: /node_modules\/@radix-ui\// },
            { name: "vendor-validation", test: /node_modules\/(zod|zustand)\// },
          ],
        },
      },
    },
  },
});
