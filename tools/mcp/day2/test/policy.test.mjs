import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, symlink, rm, realpath } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { checkedPath } from '../filesystem.mjs';
import { dockerTools, projectContainers, safeEvents } from '../docker.mjs';

test('filesystem rejects traversal, secret paths and symlink escapes', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'insighthub-day2-policy-'));
  const root = path.join(directory, 'project');
  await mkdir(root);
  await writeFile(path.join(root, 'README.md'), 'public');
  await writeFile(path.join(root, '.env'), 'CANARY_SECRET');
  await writeFile(path.join(directory, 'outside.txt'), 'CANARY_OUTSIDE');
  await symlink(path.join(directory, 'outside.txt'), path.join(root, 'escape.md'));
  await symlink(path.join(root, '.env'), path.join(root, 'secret.md'));
  try {
    assert.equal(await checkedPath(root, 'README.md'), await realpath(path.join(root, 'README.md')));
    for (const requested of ['../outside.txt', path.join(directory, 'outside.txt'), '.env', 'escape.md', 'secret.md']) {
      await assert.rejects(checkedPath(root, requested), { code: 'FILESYSTEM_SCOPE_DENIED' });
    }
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test('Docker projects only InsightHub services and rejects changed ownership', async () => {
  const id = 'a'.repeat(64);
  const labels = { 'com.docker.compose.project': 'insighthub-do2603', 'com.docker.compose.service': 'api' };
  const rows = [{ Id: id, Labels: labels, State: 'running', Status: 'Up' },
    { Id: 'b'.repeat(64), Labels: { ...labels, 'com.docker.compose.project': 'other' } },
    { Id: 'c'.repeat(64), Labels: { ...labels, 'com.docker.compose.service': 'unrelated' } }];
  assert.equal(projectContainers(rows, 'insighthub-do2603').length, 1);
  const get = async (route) => Buffer.from(JSON.stringify(route.startsWith('/containers/json') ? rows : {
    Config: { Labels: { ...labels, 'com.docker.compose.project': 'other' }, Env: ['CANARY_SECRET'] },
  }));
  const tools = dockerTools('insighthub-do2603', get);
  const result = await tools.docker_list_containers.call({});
  assert.deepEqual(result.containers, [{ service: 'api', state: 'running', status: 'Up' }]);
  assert(!JSON.stringify(result).includes('other'));
  await assert.rejects(tools.docker_inspect_container.call({ service: 'api' }), { code: 'DOCKER_SCOPE_DENIED' });
  assert(!Object.keys(tools).some((name) => /exec|restart|delete|kill/.test(name)));
});

test('Docker log projection drops raw errors, filenames, content and provider bodies', () => {
  const lines = ['raw CANARY_SECRET provider error', JSON.stringify({ event: 'ingestion_failed',
    document_id: 123, status: 'failed', attempt: 3, error_code: 'provider_error',
    filename: 'CANARY_FILENAME', content: 'CANARY_CONTENT', provider_body: 'CANARY_PROVIDER', timestamp: '2026-09-15T00:00:00Z' })].join('\n');
  const data = Buffer.from(lines);
  const header = Buffer.alloc(8); header[0] = 2; header.writeUInt32BE(data.length, 4);
  const result = safeEvents(Buffer.concat([header, data]));
  assert.equal(result.length, 1);
  assert.equal(result[0].error_code, 'provider_error');
  assert.equal(result[0].document_id, 123);
  assert(!JSON.stringify(result).includes('CANARY'));
});
