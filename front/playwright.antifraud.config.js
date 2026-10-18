import config from './playwright.config.js'
export default { ...config,
  use: { ...config.use, baseURL: 'http://localhost:5193' },
  webServer: { ...config.webServer, url: 'http://localhost:5193', env: { WEB_PORT: '5193', API_PORT: '9', GONGJING_DATA_DIR: '/private/tmp/gongjing-antifraud-e2e-data' } },
}
