import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // Giữ đường dẫn node_modules như trong dự án, để bản dựng ở lane (bản chép) và ở worktree kiểm (junction) cho cùng source map.
  resolve: { preserveSymlinks: true },
  server: {
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
