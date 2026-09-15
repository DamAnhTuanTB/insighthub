import { realpath, stat, readdir } from 'node:fs/promises';
import path from 'node:path';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { z } from 'zod';
import { PolicyError, startServer } from './stdio.mjs';

const blocked = new Set(['.git', '.codex', 'node_modules', '.venv', 'venv', 'tmp', 'evidence', 'reports', 'uploads', '__pycache__', '.next']);
const secretName = (name) => name.startsWith('.env') && name !== '.env.example'
  || /\.(pem|key|p12|pfx|tfstate|tfvars)$/.test(name)
  || /^(credentials|auth\.json|kubeconfig|mcp-readonly\.yaml)$/.test(name);

export async function checkedPath(root, requested) {
  const base = await realpath(root);
  const candidate = path.resolve(base, requested);
  const check = (target) => {
    const relative = path.relative(base, target);
    if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)
      || relative.split(path.sep).some((part) => blocked.has(part) || secretName(part))) {
      throw new PolicyError('FILESYSTEM_SCOPE_DENIED');
    }
  };
  check(candidate);
  const resolved = await realpath(candidate);
  check(resolved);
  return resolved;
}

export async function serveFilesystem(root) {
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [path.join(root, 'tools/mcp/day2/node_modules/@modelcontextprotocol/server-filesystem/dist/index.js'), root],
    stderr: 'pipe', env: { PATH: process.env.PATH ?? '', HOME: process.env.HOME ?? '' },
  });
  transport.stderr?.on('data', () => {});
  const client = new Client({ name: 'insighthub-filesystem-policy', version: '1.0.0' });
  await client.connect(transport);
  startServer('insighthub-filesystem-readonly', {
    list_directory: {
      description: 'List up to 100 entries inside the InsightHub checkout, excluding secrets and private/cache directories. Relative paths use the project root.',
      schema: z.strictObject({ path: z.string().min(1).max(1024) }),
      call: async ({ path: requested }) => {
        const target = await checkedPath(root, requested);
        const entries = await readdir(target, { withFileTypes: true });
        return { entries: entries.filter((e) => !blocked.has(e.name) && !secretName(e.name)).slice(0, 100)
          .map((e) => ({ name: e.name, type: e.isDirectory() ? 'directory' : e.isSymbolicLink() ? 'symlink' : 'file' })), truncated: entries.length > 100 };
      },
    },
    read_text_file: {
      description: 'Read a UTF-8 source/documentation file within the project, at most 64 KiB. Reject secrets, private directories, writes and symlink escapes.',
      schema: z.strictObject({ path: z.string().min(1).max(1024) }),
      call: async ({ path: requested }) => {
        const target = await checkedPath(root, requested);
        const info = await stat(target);
        if (!info.isFile() || info.size > 65536) throw new PolicyError('FILESYSTEM_SIZE_DENIED');
        const result = await client.callTool({ name: 'read_text_file', arguments: { path: target } }, undefined, { timeout: 5000 });
        if (result.isError || JSON.stringify(result).length > 70000) throw new PolicyError();
        return result;
      },
    },
  }, () => client.close());
}
