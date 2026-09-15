import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../../../', import.meta.url));
const config = JSON.parse(await readFile(path.join(root, '.mcp.json'), 'utf8'));
const absolute = process.argv.includes('--absolute');
if (process.argv[2] !== 'codex' || process.argv.slice(3).some((arg) => arg !== '--absolute')) {
  console.error('Usage: node tools/mcp/day2/host-config.mjs codex [--absolute]');
  process.exitCode = 1;
} else {
  const allowed = {
    filesystem: ['list_directory', 'read_text_file'],
    docker: ['docker_list_containers', 'docker_inspect_container', 'docker_worker_events'],
    kubernetes: ['pods_list_in_namespace', 'pods_get', 'pods_log', 'events_list'],
    prometheus: ['query'],
  };
  const lines = ['# Generated from .mcp.json by tools/mcp/day2/host-config.mjs; edit the JSON source.', '# Portable form: launch the host from the repository root. Use --absolute for GUI hosts.', ''];
  for (const [name, server] of Object.entries(config.mcpServers)) {
    lines.push(`[mcp_servers.${name}]`,
      `command = ${JSON.stringify(absolute && server.command === 'node' ? process.execPath : server.command)}`,
      `args = ${JSON.stringify(absolute ? [path.join(root, server.args[0]), ...server.args.slice(1)] : server.args)}`,
      `cwd = ${JSON.stringify(absolute ? root : '.')}`,
      'startup_timeout_sec = 30', 'tool_timeout_sec = 15',
      `enabled_tools = ${JSON.stringify(allowed[name])}`, '');
    if (server.env) lines.push(`[mcp_servers.${name}.env]`, ...Object.entries(server.env).map(([key, value]) => `${key} = ${JSON.stringify(value)}`), '');
  }
  console.log(lines.join('\n').trimEnd());
}
