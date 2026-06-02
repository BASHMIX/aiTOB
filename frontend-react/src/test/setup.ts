// Global test setup for the unified Vitest harness.
// Registers jest-dom matchers (toBeInTheDocument, etc.) with Vitest's expect,
// and polyfills browser APIs that jsdom doesn't implement but components use.
import '@testing-library/jest-dom/vitest'

// jsdom has no ResizeObserver; components such as HubDashboard rely on it.
class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver =
  ResizeObserver as unknown as typeof globalThis.ResizeObserver
