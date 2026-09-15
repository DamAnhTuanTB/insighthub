import http from 'node:http';
import { z } from 'zod';
import { PolicyError, startServer } from './stdio.mjs';

const services = ['web', 'api', 'postgres', 'redis', 'ingestion-worker'];
const events = new Set(['worker_started', 'worker_stopped', 'ingestion_retry', 'ingestion_completed', 'ingestion_failed']);
const errorCodes = new Set(['internal_error', 'provider_error', 'invalid_document', 'document_not_found',
  'document_conflict', 'index_identity_conflict', 'schema_mismatch', 'queue_unavailable']);

export function dockerGet(socketPath, route, limit = 262144) {
  return new Promise((resolve, reject) => {
    const request = http.get({ socketPath, path: route, timeout: 5000 }, (response) => {
      const chunks = [];
      let size = 0;
      response.on('data', (chunk) => {
        size += chunk.length;
        if (size > limit) { response.destroy(); reject(new PolicyError('DOCKER_RESPONSE_TOO_LARGE')); }
        else chunks.push(chunk);
      });
      response.on('end', () => response.statusCode === 200 ? resolve(Buffer.concat(chunks)) : reject(new PolicyError('DOCKER_READ_FAILED')));
      response.on('error', () => reject(new PolicyError('DOCKER_READ_FAILED')));
    });
    request.on('timeout', () => { request.destroy(); reject(new PolicyError('DOCKER_TIMEOUT')); });
    request.on('error', () => reject(new PolicyError('DOCKER_READ_FAILED')));
  });
}

export function projectContainers(rows, project) {
  return rows.filter((row) => row.Labels?.['com.docker.compose.project'] === project
    && services.includes(row.Labels?.['com.docker.compose.service']));
}

export function safeEvents(buffer) {
  // Docker's non-TTY log stream consists of 8-byte headers followed by frames.
  const frames = [];
  for (let offset = 0; offset + 8 <= buffer.length;) {
    const length = buffer.readUInt32BE(offset + 4);
    if (buffer[offset] > 2 || buffer[offset + 1] || buffer[offset + 2] || buffer[offset + 3]
      || offset + 8 + length > buffer.length) break;
    frames.push(buffer.subarray(offset + 8, offset + 8 + length));
    offset += 8 + length;
  }
  const output = [];
  for (const line of Buffer.concat(frames).toString('utf8').split('\n')) {
    let row;
    try { row = JSON.parse(line); } catch { continue; }
    if (!events.has(row.event)) continue;
    const safe = { event: row.event };
    if (Number.isSafeInteger(row.document_id) && row.document_id >= 0) safe.document_id = row.document_id;
    if (['pending', 'ready', 'failed'].includes(row.status)) safe.status = row.status;
    if (Number.isInteger(row.attempt) && row.attempt >= 1 && row.attempt <= 3) safe.attempt = row.attempt;
    if (errorCodes.has(row.error_code)) safe.error_code = row.error_code;
    if (typeof row.timestamp === 'string' && row.timestamp.length <= 40
      && /^\d{4}-\d{2}-\d{2}T[\d:.+-]+Z?$/.test(row.timestamp)) safe.timestamp = row.timestamp;
    output.push(safe);
  }
  return output.slice(-50);
}

export function dockerTools(project, get) {
  const list = async () => {
    const filters = encodeURIComponent(JSON.stringify({ label: [`com.docker.compose.project=${project}`] }));
    return projectContainers(JSON.parse((await get(`/containers/json?all=true&filters=${filters}`)).toString()), project);
  };
  const inspect = async (service) => {
    const containers = await list();
    const match = containers.find((row) => row.Labels['com.docker.compose.service'] === service);
    if (!match || !/^[a-f0-9]{64}$/.test(match.Id)) throw new PolicyError('DOCKER_SERVICE_NOT_FOUND');
    const row = JSON.parse((await get(`/containers/${match.Id}/json`)).toString());
    if (row.Config?.Labels?.['com.docker.compose.project'] !== project
      || row.Config?.Labels?.['com.docker.compose.service'] !== service) throw new PolicyError('DOCKER_SCOPE_DENIED');
    return row;
  };
  return {
    docker_list_containers: {
      description: 'Read only the five default InsightHub Compose services. Return service, state and status; omit environment, commands, mounts and other stacks.',
      schema: z.strictObject({}),
      call: async () => ({ project, containers: (await list()).map((row) => ({ service: row.Labels['com.docker.compose.service'], state: row.State, status: row.Status })) }),
    },
    docker_inspect_container: {
      description: 'Read the state, exit code, OOM flag and restart count of one InsightHub service. No credentials, provider errors or raw inspection body.',
      schema: z.strictObject({ service: z.enum(services) }),
      call: async ({ service }) => {
        const row = await inspect(service);
        return { service, state: row.State.Status, running: row.State.Running, exit_code: row.State.ExitCode,
          oom_killed: row.State.OOMKilled, restart_count: row.RestartCount,
          ...(row.State.Health ? { health: row.State.Health.Status } : {}) };
      },
    },
    docker_worker_events: {
      description: 'Read at most 50 sanitized JSON lifecycle/ingestion events from the InsightHub worker. Raw exceptions, content, filenames, provider bodies and credentials are discarded.',
      schema: z.strictObject({ tail: z.number().int().min(1).max(50).default(20) }),
      call: async ({ tail }) => {
        const row = await inspect('ingestion-worker');
        if (row.Config.Tty) throw new PolicyError('DOCKER_LOG_FORMAT_DENIED');
        const logs = await get(`/containers/${row.Id}/logs?stdout=true&stderr=true&tail=${tail}`, 65536);
        return { service: 'ingestion-worker', events: safeEvents(logs), raw_logs_omitted: true };
      },
    },
  };
}

export function serveDocker() {
  const socketPath = process.env.INSIGHTHUB_DOCKER_SOCKET ?? '/var/run/docker.sock';
  if (!socketPath.startsWith('/') || socketPath.includes('\0')) throw new PolicyError();
  const project = process.env.INSIGHTHUB_DOCKER_PROJECT ?? 'insighthub-do2603';
  if (!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(project)) throw new PolicyError();
  startServer('insighthub-docker-readonly', dockerTools(project, (route, limit) => dockerGet(socketPath, route, limit)));
}
