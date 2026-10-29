import { execSync } from "child_process"
import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

import pkg from "./package.json"

// The deployed commit, so the menu can say exactly what is live. Railway
// passes RAILWAY_GIT_COMMIT_SHA as a Docker build arg; locally, ask git.
function commit(): string {
  const sha = process.env.RAILWAY_GIT_COMMIT_SHA
  if (sha) return sha.slice(0, 7)
  try {
    return execSync("git rev-parse --short HEAD").toString().trim()
  } catch {
    return "dev"
  }
}

// https://vite.dev/config/
export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
    __APP_COMMIT__: JSON.stringify(commit()),
  },
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
})
