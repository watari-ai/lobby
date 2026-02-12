import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          // Core React
          'react-vendor': ['react', 'react-dom'],
          // PixiJS (2D rendering)
          'pixi': ['pixi.js'],
          // Live2D Cubism SDK
          'live2d': ['pixi-live2d-display'],
          // State management
          'zustand': ['zustand'],
        },
      },
    },
    chunkSizeWarningLimit: 600, // Increase limit slightly for Live2D SDK
  },
});
