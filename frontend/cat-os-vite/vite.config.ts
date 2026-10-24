import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';
import { localIntegration } from './vite.local-integration';

export default defineConfig({
  plugins: [react(), tailwindcss(), localIntegration()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@tanstack/react-router': path.resolve(__dirname, './src/lib/router.tsx'),
    },
  },
  server: {
    port: 8890,
    host: '127.0.0.1',
    strictPort: true,
  },
});
