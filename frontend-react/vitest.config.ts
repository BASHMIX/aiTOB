import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config'

// Unified test harness: inherits the react plugin + "@" alias from vite.config.ts
// so tests resolve "@/..." imports exactly like the app does.
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      globals: true,
      environment: 'jsdom',
      css: true,
      setupFiles: ['./src/test/setup.ts'],
    },
  })
)
