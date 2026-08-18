import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import fs from 'fs'

// Plugin to serve static files from /Volumes/SDCARD during dev
function storagePlugin() {
  const storageRoot = '/Volumes/SDCARD'
  const exists = fs.existsSync(storageRoot)
  if (!exists) console.warn('⚠ Storage volume not mounted at', storageRoot)
  else console.log('✅ Storage volume mounted at', storageRoot)

  return {
    name: 'storage-plugin',
    enforce: 'pre' as const,
    configureServer(server: any) {
      // Handle /storage/ requests BEFORE Vite's default middleware
      server.middlewares.use((req: any, res: any, next: any) => {
        const url = req.url || ''
        if (!url.startsWith('/storage/')) return next()

        const urlPath = decodeURIComponent(url)
        const fullPath = path.join(storageRoot, urlPath)

        if (!fs.existsSync(fullPath)) {
          console.warn('⚠ Storage file not found:', fullPath)
          res.statusCode = 404
          res.setHeader('Content-Type', 'text/plain')
          res.end('Not found')
          return
        }

        const stat = fs.statSync(fullPath)
        if (!stat.isFile()) {
          res.statusCode = 404
          res.end()
          return
        }

        const ext = path.extname(fullPath).toLowerCase()
        const mime: Record<string, string> = {
          '.jpg': 'image/jpeg',
          '.jpeg': 'image/jpeg',
          '.png': 'image/png',
          '.gif': 'image/gif',
          '.webp': 'image/webp',
          '.svg': 'image/svg+xml',
          '.csv': 'text/csv',
          '.json': 'application/json',
        }

        const contentType = mime[ext] || 'application/octet-stream'
        console.log(`📦 Serving ${urlPath} (${contentType}, ${stat.size}B)`)

        res.statusCode = 200
        res.setHeader('Content-Type', contentType)
        res.setHeader('Cache-Control', 'public, max-age=3600')
        res.setHeader('Access-Control-Allow-Origin', '*')

        const stream = fs.createReadStream(fullPath)
        stream.pipe(res)
        stream.on('error', (err: any) => {
          console.error('⚠ Stream error:', err.message)
          if (!res.headersSent) {
            res.statusCode = 500
            res.end()
          }
        })
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), storagePlugin()],
  server: {
    port: 5199,
    strictPort: true,
  },
})