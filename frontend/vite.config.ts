/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: [
        'src/store/authStore.ts',
        'src/pages/LoginPage.tsx',
        'src/pages/DashboardPage.tsx',
        'src/routes/ProtectedRoute.tsx',
      ],
      exclude: [
        'node_modules/',
        'src/test/',
        'src/mocks/',
        '*.config.*',
        'src/main.tsx',
        'src/vite-env.d.ts',
      ],
      thresholds: {
        'src/store/authStore.ts': {
          statements: 80, branches: 75, functions: 80, lines: 80,
        },
        'src/pages/LoginPage.tsx': {
          statements: 80, branches: 75, functions: 80, lines: 80,
        },
        'src/routes/ProtectedRoute.tsx': {
          statements: 80, branches: 75, functions: 80, lines: 80,
        },
        'src/pages/DashboardPage.tsx': {
          statements: 80, branches: 75, functions: 30, lines: 80,
        },
      },
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      external: (id: string) => id === 'msw' || id === 'msw/browser',
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          charts: ['recharts'],
        },
      },
    },
  },
})
