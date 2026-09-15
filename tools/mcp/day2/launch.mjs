import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { access } from 'node:fs/promises';

const root = fileURLToPath(new URL('../../../', import.meta.url));
const backend = process.argv[2];
try {
  if (process.argv.length !== 3) throw new Error();
  process.chdir(root);
  if (backend === 'filesystem') {
    const { serveFilesystem } = await import('./filesystem.mjs');
    await serveFilesystem(root);
  } else if (backend === 'docker') {
    const { serveDocker } = await import('./docker.mjs');
    serveDocker();
  } else if (backend === 'kubernetes' || backend === 'prometheus') {
    const command = path.join(root, 'tmp/day2/bin', backend);
    await access(command);
    const args = backend === 'kubernetes' ? [
      '--config', path.join(root, 'tools/mcp/day2/kubernetes.toml'),
      '--kubeconfig', path.join(root, 'tmp/day2/mcp-readonly.yaml'),
      '--read-only', '--disable-multi-cluster', '--toolsets=core', '--list-output=table',
    ] : [
      '--mcp.transport=stdio', '--mcp.tools=query',
      '--prometheus.url=http://127.0.0.1:9090', '--prometheus.timeout=5s', '--prometheus.truncation-limit=20',
      '--web.listen-address=127.0.0.1:0', '--log.level=error',
    ];
    if (backend === 'kubernetes') await access(path.join(root, 'tmp/day2/mcp-readonly.yaml'));
    const child = spawn(command, args, {
      stdio: ['inherit', 'inherit', 'pipe'],
      env: { PATH: process.env.PATH ?? '', HOME: path.join(root, 'tmp/day2/home') },
    });
    child.stderr.on('data', () => {});
    child.on('error', () => { console.error('MCP_BACKEND_START_FAILED'); process.exitCode = 1; });
    child.on('exit', (code) => { process.exitCode = code ?? 1; });
    for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
  } else throw new Error();
} catch {
  console.error('DAY2_MCP_STARTUP_REJECTED: run the setup in tools/mcp/day2/README.md');
  process.exitCode = 1;
}
