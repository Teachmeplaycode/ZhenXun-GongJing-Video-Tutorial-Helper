import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Ports come from the environment so ./dev.sh (or a second copy for testing) can move them:
// WEB_PORT for this dev server, API_PORT for the backend that /api is proxied to.
const apiPort = process.env.API_PORT || 8000
const webPort = Number(process.env.WEB_PORT || 5173)

export default defineConfig({
  plugins: [react()],
  server: {
    port: webPort,
    strictPort: true, // fail loudly instead of drifting to another port the scripts don't know about
    proxy: { '/api': `http://127.0.0.1:${apiPort}` },
  },
})
