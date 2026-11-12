import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    allowedHosts: [process.env.WEB_HOST || 'localhost'],
    // Polling also works with Docker bind mounts and exhausted inotify watches.
    watch: { usePolling: process.env.CHOKIDAR_USEPOLLING !== 'false', interval: 300 },
    proxy: { '/api': { target: process.env.API_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: false, ws: true } },
  },
});
