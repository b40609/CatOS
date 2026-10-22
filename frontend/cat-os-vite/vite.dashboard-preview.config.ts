import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';

export default defineConfig({
  plugins: [react(), tailwindcss(), {
    name: 'catos-dashboard-preview-entry',
    transformIndexHtml: (html) => html.replace('/src/main.tsx', '/src/preview/main.tsx'),
  }],
  resolve: { alias: {
    '@': path.resolve(__dirname, 'src'),
    '@tanstack/react-router': path.resolve(__dirname, 'src/lib/router.tsx'),
  } },
  server: {
    host: '127.0.0.1',
    port: 8887,
    strictPort: true,
    watch: {
      ignored: ['**/dist/**', '**/outputs/**', '**/.git/**', '**/reports/**'],
    },
  },
  build: { outDir: '../outputs/dashboard-native-preview', emptyOutDir: false },
});
