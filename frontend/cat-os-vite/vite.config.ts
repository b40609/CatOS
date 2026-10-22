import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@tanstack/react-router': path.resolve(__dirname, './src/lib/router.tsx'),
    },
  },
  server: {
    port: 8890,
    host: '127.0.0.1',
    proxy: {
      '/api/research': {
        target: 'http://127.0.0.1:8770',
        changeOrigin: true,
        headers: {
          origin: 'http://127.0.0.1:8770',
        },
      },
      '/intel': {
        target: 'http://127.0.0.1:8770',
        changeOrigin: true,
      },
      '/api/workspace': {
        target: 'http://127.0.0.1:8770',
        changeOrigin: true,
      },
    },
  },
});
