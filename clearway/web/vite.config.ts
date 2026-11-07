import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteStaticCopy } from "vite-plugin-static-copy";

export default defineConfig({
  plugins: [
    react(),
    viteStaticCopy({
      targets: [
        { src: "../licenses/AGPL-3.0.txt", dest: "assets/licenses", rename: { stripBase: true } },
        ...["Workers", "ThirdParty", "Assets", "Widgets"].map((folder) => ({
          src: `node_modules/cesium/Build/Cesium/${folder}/**/*`,
          dest: "cesium",
          rename: { stripBase: 4 },
        })),
        {
          src: "node_modules/cesium/LICENSE.md",
          dest: "assets/licenses",
          rename: { stripBase: true, name: "cesium-LICENSE.md" },
        },
        {
          src: "node_modules/cesium/ThirdParty*.json",
          dest: "assets/licenses",
          rename: { stripBase: true },
        },
        {
          src: "node_modules/@fontsource-variable/archivo/LICENSE",
          dest: "assets/licenses",
          rename: { stripBase: true, name: "archivo-OFL.txt" },
        },
        {
          src: "node_modules/@fontsource-variable/martian-mono/LICENSE",
          dest: "assets/licenses",
          rename: { stripBase: true, name: "martian-mono-OFL.txt" },
        },
      ],
    }),
  ],
  define: { CESIUM_BASE_URL: JSON.stringify("/cesium/") },
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  build: {
    license: { fileName: "assets/licenses/bundled-dependencies.md" },
    chunkSizeWarningLimit: 1800,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("/cesium/") || id.includes("/@cesium/"))
            return "cesium";
        },
      },
    },
  },
});
