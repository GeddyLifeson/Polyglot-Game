// Serves the repo root over HTTP on a free port and runs the given qa script against it.
// Usage: node qa/with_server.js qa/qa_clips.js   (qa_clips needs HTTP to fetch audio/manifest.json)
const { spawn, spawnSync } = require('child_process'); const net = require('net'); const path = require('path');
const root = path.resolve(__dirname, '..'); const script = process.argv[2] || 'qa/qa_clips.js';
const srv = net.createServer(); srv.listen(0, '127.0.0.1', () => {
  const port = srv.address().port; srv.close(() => {
    const http = spawn('python3', ['-m', 'http.server', String(port), '--bind', '127.0.0.1'], { cwd: root, stdio: 'ignore' });
    const wait = (n) => { const s = net.connect(port, '127.0.0.1'); s.on('connect', () => { s.destroy(); run(); }); s.on('error', () => n > 0 ? setTimeout(() => wait(n - 1), 250) : (console.error('server did not start'), http.kill(), process.exit(1))); };
    const run = () => { const r = spawnSync(process.execPath, [path.resolve(root, script)], { cwd: root, stdio: 'inherit', env: { ...process.env, QA_URL: 'http://127.0.0.1:' + port } }); http.kill(); process.exit(r.status == null ? 1 : r.status); };
    wait(40);
  });
});
