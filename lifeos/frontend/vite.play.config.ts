// Build the phone app (LIFE OS: Story) as a static site: python ../tools/build_phone_app.py runs this.
import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "./",
  publicDir: "public-play",
  build: {
    outDir: path.resolve(__dirname, "../../docs/play"),
    emptyOutDir: true,
    chunkSizeWarningLimit: 1500,
    rollupOptions: { input: path.resolve(__dirname, "play.html") },
  },
});
