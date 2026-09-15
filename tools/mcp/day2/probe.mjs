// SDK/backend evidence only. This is not evidence of a model calling tools in a host.
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { CallToolResultSchema } from '@modelcontextprotocol/sdk/types.js';

const root = fileURLToPath(new URL('../../../', import.meta.url));
const config = JSON.parse(await readFile(path.join(root, '.mcp.json'), 'utf8'));
const selected = process.argv[2] ? [process.argv[2]] : Object.keys(config.mcpServers);
const observations = [];
let failed = false;
for (const backend of selected) {
  if (!config.mcpServers[backend]) throw new Error('Unknown backend');
  const entry = config.mcpServers[backend];
  const transport = new StdioClientTransport({ command: process.execPath,
    args: [path.join(root, entry.args[0]), ...entry.args.slice(1)], cwd: root,
    env: { PATH: process.env.PATH ?? '', HOME: process.env.HOME ?? '', ...entry.env }, stderr: 'pipe' });
  transport.stderr?.on('data', () => {});
  const client = new Client({ name: 'insighthub-day2-sdk-probe', version: '1.0.0' });
  const observation = { backend, client: 'official-sdk', host_verified: false, observed_at: new Date().toISOString(), transport: 'stdio', calls: [] };
  const start = transport.start.bind(transport);
  transport.start = async () => {
    await start();
    const onmessage = transport.onmessage;
    transport.onmessage = (message) => {
      if (message.result?.protocolVersion) observation.protocol = message.result.protocolVersion;
      onmessage?.(message);
    };
  };
  try {
    await client.connect(transport);
    observation.connected = true;
    const list = await client.listTools();
    observation.tools = list.tools.map(({ name, inputSchema }) => ({ name, inputSchema }));
    const calls = {
      filesystem: [['list_directory', { path: '.' }], ['read_text_file', { path: 'AGENTS.md' }]],
      docker: [['docker_list_containers', {}], ['docker_inspect_container', { service: 'ingestion-worker' }], ['docker_worker_events', { tail: 10 }]],
      kubernetes: [['pods_list_in_namespace', { namespace: 'insighthub' }]],
      prometheus: [['query', { query: 'up' }]],
    }[backend];
    for (const [name, args] of calls) {
      const result = await client.callTool({ name, arguments: args }, undefined, { timeout: 15000 });
      observation.calls.push({ name, input: args, output: result, timestamp: new Date().toISOString(), passed: !result.isError });
      if (result.isError) failed = true;
    }
    const denies = {
      filesystem: [['read_text_file', { path: '/tmp/insighthub-day2-outside-scope.txt' }], ['read_text_file', { path: '.env' }], ['write_file', { path: 'day2-should-never-exist.txt', content: 'denied' }]],
      docker: [['docker_inspect_container', { service: 'unrelated-stack' }], ['docker_exec', { command: 'echo denied' }]],
      kubernetes: [['pods_delete', { namespace: 'insighthub', name: 'day2-lab-sample' }], ['resources_get', { apiVersion: 'v1', kind: 'Secret', namespace: 'insighthub', name: 'day2-deny-canary' }], ['pods_list_in_namespace', { namespace: 'kube-system' }]],
      prometheus: [['reload', {}], ['delete_series', { match: ['up'] }]],
    }[backend];
    for (const [name, args] of denies) {
      let denied = false;
      try {
        const result = await client.request({ method: 'tools/call', params: { name, arguments: args } }, CallToolResultSchema, { timeout: 15000 });
        denied = result.isError === true;
      } catch (error) { denied = [-32601, -32602].includes(error.code); }
      observation.calls.push({ name, input: args, expected: 'denied', denied, timestamp: new Date().toISOString() });
      if (!denied) failed = true;
    }
  } catch {
    observation.error_code = 'BACKEND_PROBE_FAILED';
    failed = true;
  } finally { await client.close(); }
  observations.push(observation);
  console.log(JSON.stringify({ backend, connected: observation.connected ?? false,
    tools: observation.tools?.map((tool) => tool.name), calls: observation.calls.map(({ name, passed, denied }) => ({ name, passed, denied })), error_code: observation.error_code }));
}
await mkdir(path.join(root, 'evidence'), { recursive: true });
const filename = selected.length === 1 ? `day2-sdk-${selected[0]}.json` : 'day2-sdk.json';
await writeFile(path.join(root, 'evidence', filename), JSON.stringify({ mode: 'live', milestone_complete: false, host_verified: false, observations }, null, 2) + '\n');
if (failed) process.exitCode = 1;
