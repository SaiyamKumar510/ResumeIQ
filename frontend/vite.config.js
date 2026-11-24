import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// In development, requests to /api are proxied to the Flask server, so no CORS
// setup is needed. Change VITE_PROXY_TARGET if Flask runs on another port.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: env.VITE_PROXY_TARGET || 'http://127.0.0.1:5000',
          changeOrigin: true,
        },
      },
    },
  };
});
