// Serves the repo root over HTTP on a free port and runs the given qa script against it.
// Usage: node qa/with_server.js qa/qa_clips.js   (qa_clips needs HTTP to fetch audio/manifest.json)
// The server runs in-process: python3 is not on PATH everywhere, and python's http.server stalls under the parallel clip fetches.
const http = require('http'); const fs = require('fs'); const { spawn } = require('child_process'); const path = require('path');
const root = path.resolve(__dirname, '..'); const script = process.argv[2] || 'qa/qa_clips.js';
const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.css': 'text/css', '.ogg': 'audio/ogg', '.wav': 'audio/wav', '.txt': 'text/plain' };
const srv = http.createServer((req, res) => {
  const p = path.join(root, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(root)) return res.writeHead(403).end();
  const f = fs.existsSync(p) && fs.statSync(p).isDirectory() ? path.join(p, 'index.html') : p;
  fs.readFile(f, (err, buf) => err ? res.writeHead(404).end() : res.writeHead(200, { 'Content-Type': types[path.extname(f)] || 'application/octet-stream' }).end(buf));
}).listen(0, '127.0.0.1', () => {
  // async spawn, not spawnSync: a blocked event loop would leave this server unable to answer
  const child = spawn(process.execPath, [path.resolve(root, script)], { cwd: root, stdio: 'inherit', env: { ...process.env, QA_URL: 'http://127.0.0.1:' + srv.address().port } });
  child.on('exit', (code) => process.exit(code == null ? 1 : code));
});
