import { defineConfig, devices } from '@playwright/test'

// End-to-end tests of the UI against an in-browser mock backend (e2e/mock-api.js): offline and free.
// The dev server gets its own port so it never collides with ./dev.sh on 5173.
const PORT = 5199

export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  workers: 4,
  reporter: [['list']],
  use: {
    baseURL: `http://localhost:${PORT}`,
    viewport: { width: 1440, height: 960 },
    // The app honours reduced motion: intros and transitions jump to their end state, so tests don't wait on animation.
    reducedMotion: 'reduce',
    trace: 'retain-on-failure',
    // No WebGL: in headless Chromium the sculpture renders in software and reads pixels back every frame,
    // which starved the pages (buttons never became "stable"). The app then shows its static fallback
    // (design_2.md §7), so that path is exercised too.
    launchOptions: { args: ['--disable-webgl', '--disable-webgl2', '--disable-3d-apis'] },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 960 } } }],
  webServer: {
    command: 'npm run dev --silent',
    url: `http://localhost:${PORT}`,
    env: { WEB_PORT: String(PORT), API_PORT: '9' }, // /api never reaches a real backend: the mock answers in the page
    reuseExistingServer: false,
    timeout: 60_000,
  },
})
