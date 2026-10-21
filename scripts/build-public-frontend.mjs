#!/usr/bin/env node
// Build only from frontend sources; ignore every local .env file.
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
import { build } from '../frontend/node_modules/vite/dist/node/index.js'

const root = fileURLToPath(new URL('../frontend/', import.meta.url))
const api = process.env.VITE_API_BASE_URL
let url
try { url = new URL(api) } catch { throw new Error('Set VITE_API_BASE_URL to the backend HTTPS origin.') }
const loopback = ['127.0.0.1', 'localhost'].includes(url.hostname)
if (loopback && process.env.FOOTBALL_ALLOW_LOCAL_API !== 'true') {
  throw new Error('Public builds require a deployed backend; set FOOTBALL_ALLOW_LOCAL_API=true only for local rehearsal.')
}
if ((url.protocol !== 'https:' && !(loopback && url.protocol === 'http:')) ||
    url.username || url.password || url.search || url.hash || url.pathname !== '/') {
  throw new Error('VITE_API_BASE_URL must be a backend HTTPS origin without credentials or paths.')
}
// Only an explicit public API URL can enter the build environment.
for (const key of Object.keys(process.env)) {
  if (key.startsWith('VITE_')) delete process.env[key]
}
process.env.VITE_API_BASE_URL = url.origin
await build({ root, envDir: false, build: { outDir: resolve(process.argv[2] || `${root}/dist`) } })
