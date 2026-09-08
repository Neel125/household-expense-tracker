import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// During `npm run dev`, proxy /api to the FastAPI backend so the browser
// only ever talks to one origin (avoids CORS entirely in dev). In
// production the built app is served BY the backend (see backend/main.py),
// so /api is same-origin there too.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
