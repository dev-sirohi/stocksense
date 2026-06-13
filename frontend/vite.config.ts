import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
    plugins: [react()],
    build: {
        sourcemap: true,
    },
    server: {
        port: 5173,
        proxy: {
            // All /api requests are forwarded to the FastAPI backend during development.
            // This means axios calls to '/api/inventory/alerts' hit localhost:8000 —
            // no CORS issues in dev, and no hardcoded backend URL in the frontend code.
            '/api': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
        },
    },
});
