import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Point /api at the backend once it exists (VITE_API_BASE enables the real SSE client)
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
