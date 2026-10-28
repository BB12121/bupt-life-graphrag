import http from 'node:http'
import https from 'node:https'
import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../dist')
const port = Number(process.env.PORT || 4173)
const backend = new URL(process.env.BUPT_BACKEND_URL || 'http://127.0.0.1:8000')
if (!['http:', 'https:'].includes(backend.protocol)) throw new Error('BUPT_BACKEND_URL must use HTTP(S)')
const mime = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.svg': 'image/svg+xml', '.json': 'application/json; charset=utf-8', '.jpg': 'image/jpeg', '.png': 'image/png' }
try { await fs.access(path.join(root, 'index.html')) } catch { console.error('未找到 dist。请先运行 npm install 和 npm run build，或使用包含 dist 的完整交付包。'); process.exit(1) }
const server = http.createServer(async (req, res) => {
  try {
    const pathname = decodeURIComponent(new URL(req.url || '/', 'http://127.0.0.1').pathname)
    if (pathname === '/api' || pathname.startsWith('/api/')) {
      const upstream = (backend.protocol === 'https:' ? https : http).request({
        protocol: backend.protocol, hostname: backend.hostname, port: backend.port,
        path: req.url, method: req.method, headers: { ...req.headers, host: backend.host },
        timeout: 240_000,
      }, incoming => { res.writeHead(incoming.statusCode || 502, incoming.headers); incoming.pipe(res) })
      upstream.on('timeout', () => upstream.destroy(new Error('Backend timeout')))
      upstream.on('error', () => {
        if (res.headersSent) { res.destroy(); return }
        res.writeHead(503, { 'Content-Type': 'application/json; charset=utf-8' })
        res.end(JSON.stringify({ error: { code: 'backend_not_connected', message: '无法连接后端，请先启动 FastAPI 服务。' } }))
      })
      req.on('aborted', () => upstream.destroy())
      req.pipe(upstream)
      return
    }
    if (!['GET', 'HEAD'].includes(req.method || '')) { res.writeHead(405, { Allow: 'GET, HEAD' }); res.end(); return }
    let target = path.resolve(root, '.' + pathname)
    if (target !== root && !target.startsWith(root + path.sep)) { res.writeHead(403); res.end(); return }
    let body
    try { if ((await fs.stat(target)).isDirectory()) target = path.join(target, 'index.html'); body = await fs.readFile(target) }
    catch { if (path.extname(pathname)) { res.writeHead(404); res.end('Not found'); return } target = path.join(root, 'index.html'); body = await fs.readFile(target) }
    res.writeHead(200, { 'Content-Type': mime[path.extname(target)] || 'application/octet-stream', 'X-Content-Type-Options':'nosniff', 'Cache-Control':'no-cache' })
    res.end(req.method === 'HEAD' ? undefined : body)
  } catch { res.writeHead(400); res.end('Bad request') }
})
server.on('error', error => { console.error('展示服务启动失败：' + error.message); process.exit(1) })
server.listen(port, '127.0.0.1', () => console.log('北邮生活指南：http://127.0.0.1:' + port + '\nAPI 转发至 ' + backend.origin + '；按 Ctrl+C 停止。'))
