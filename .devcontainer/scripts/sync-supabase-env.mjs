#!/usr/bin/env node
import { promisify } from 'node:util';
import { execFile } from 'node:child_process';
import { readFile, writeFile, access, mkdir } from 'node:fs/promises';
import { constants } from 'node:fs';
import path from 'node:path';

const execFileAsync = promisify(execFile);

function parseArgs() {
  const outIdx = process.argv.indexOf('--out');
  const out = outIdx > -1 ? process.argv[outIdx + 1] : null;
  return { out };
}

const DEFAULT_TARGET_FILES = ['.env.local'];

const { out } = parseArgs();
const TARGET_FILES = out ? [out] : DEFAULT_TARGET_FILES;

const LABEL_TO_ENV_KEY = new Map([
  ['api url', 'NEXT_PUBLIC_SUPABASE_URL'],
  ['rest url', 'NEXT_PUBLIC_SUPABASE_URL'],
  ['graphql url', 'NEXT_PUBLIC_SUPABASE_GRAPHQL_URL'],
  ['database url', 'SUPABASE_DB_URL_LOCAL'],
  ['database password', 'SUPABASE_DB_PASSWORD_LOCAL'],
  ['publishable key', 'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY'],
  ['secret key', 'SUPABASE_SECRET_KEY'],
  ['anon key', 'NEXT_PUBLIC_SUPABASE_ANON_KEY'],
  ['service role key', 'SUPABASE_SERVICE_ROLE_KEY'],
  ['studio url', 'SUPABASE_STUDIO_URL'],
  ['studio api url', 'SUPABASE_STUDIO_URL'],
  ['mailpit url', 'SUPABASE_MAILPIT_URL'],
  ['inbucket url', 'SUPABASE_MAILPIT_URL'],
  ['storage url', 'SUPABASE_STORAGE_URL'],
  ['storage api url', 'SUPABASE_STORAGE_URL'],
  ['storage s3 url', 'SUPABASE_STORAGE_URL'],
  ['s3 storage url', 'SUPABASE_STORAGE_URL'],
  ['s3 access key', 'SUPABASE_S3_ACCESS_KEY'],
  ['s3 secret key', 'SUPABASE_S3_SECRET_KEY'],
  ['s3 region', 'SUPABASE_S3_REGION'],
  ['s3 access key id', 'SUPABASE_S3_ACCESS_KEY'],
  ['storage access key', 'SUPABASE_S3_ACCESS_KEY'],
  ['storage secret key', 'SUPABASE_S3_SECRET_KEY'],
  ['storage s3 access key', 'SUPABASE_S3_ACCESS_KEY'],
  ['storage s3 secret key', 'SUPABASE_S3_SECRET_KEY'],
  ['realtime url', 'SUPABASE_REALTIME_URL'],
  ['functions url', 'SUPABASE_FUNCTIONS_URL'],
  ['edge functions url', 'SUPABASE_FUNCTIONS_URL']
]);

const KNOWN_ENV_KEYS = new Set([
  'NEXT_PUBLIC_SUPABASE_URL',
  'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY',
  'NEXT_PUBLIC_SUPABASE_ANON_KEY',
  'SUPABASE_SECRET_KEY',
  'SUPABASE_SERVICE_ROLE_KEY',
  'NEXT_PUBLIC_SUPABASE_GRAPHQL_URL',
  'SUPABASE_DB_URL_LOCAL',
  'SUPABASE_DB_PASSWORD_LOCAL',
  'SUPABASE_STUDIO_URL',
  'SUPABASE_MAILPIT_URL',
  'SUPABASE_STORAGE_URL',
  'SUPABASE_S3_ACCESS_KEY',
  'SUPABASE_S3_SECRET_KEY',
  'SUPABASE_S3_REGION',
  'SUPABASE_REALTIME_URL',
  'SUPABASE_FUNCTIONS_URL'
]);

function hasRequired(map) {
  const hasUrl = map.has('NEXT_PUBLIC_SUPABASE_URL');
  const hasPublic = map.has('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY') || map.has('NEXT_PUBLIC_SUPABASE_ANON_KEY');
  return hasUrl && hasPublic;
}

function preferNewAndBackfill(envMap) {
  const anon = envMap.get('NEXT_PUBLIC_SUPABASE_ANON_KEY');
  const publishable = envMap.get('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY');
  if (!publishable && anon) envMap.set('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY', anon);
  if (!anon && publishable) envMap.set('NEXT_PUBLIC_SUPABASE_ANON_KEY', publishable);

  const service = envMap.get('SUPABASE_SERVICE_ROLE_KEY');
  const secret = envMap.get('SUPABASE_SECRET_KEY');
  if (!secret && service) envMap.set('SUPABASE_SECRET_KEY', service);
  if (!service && secret) envMap.set('SUPABASE_SERVICE_ROLE_KEY', secret);
}

function normalizeLabel(label) {
  return label.toLowerCase().replace(/[_\s]+/g, ' ').trim();
}

function parsePrettyStatus(output) {
  const envValues = new Map();
  for (const rawLine of output.split(/\r?\n/)) {
    const match = rawLine.match(/^\s*([^:]+):\s*(.+)$/);
    if (!match) continue;
    const labelKey = normalizeLabel(match[1]);
    const value = match[2].trim();
    if (!value) continue;

    const envKey = LABEL_TO_ENV_KEY.get(labelKey);
    if (envKey && !envValues.has(envKey)) {
      envValues.set(envKey, value);
    }

    if (labelKey === 'database url') {
      try {
        const parsedUrl = new URL(value);
        if (!envValues.has('SUPABASE_DB_PASSWORD_LOCAL') && parsedUrl.password) {
          envValues.set('SUPABASE_DB_PASSWORD_LOCAL', parsedUrl.password);
        }
      } catch (error) {
        console.warn('[sync-supabase-env] Unable to parse database URL for password extraction:', error.message);
      }
    }
  }
  return envValues;
}

function parseEnvBlock(output) {
  const envValues = new Map();
  for (const rawLine of output.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const equalsIndex = line.indexOf('=');
    if (equalsIndex === -1) continue;
    const key = line.slice(0, equalsIndex).trim();
    let value = line.slice(equalsIndex + 1);
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (key) envValues.set(key, value);
  }
  return envValues;
}

function mapStatusKeysToEnv(statusValues) {
  const mapped = new Map();
  for (const [key, value] of statusValues) {
    const normalized = normalizeLabel(key);
    const envKey = LABEL_TO_ENV_KEY.get(normalized);
    if (envKey && !mapped.has(envKey)) {
      mapped.set(envKey, value);
      continue;
    }
    if (KNOWN_ENV_KEYS.has(key) && !mapped.has(key)) {
      mapped.set(key, value);
    }
  }

  if (mapped.has('SUPABASE_DB_URL_LOCAL') && !mapped.has('SUPABASE_DB_PASSWORD_LOCAL')) {
    try {
      const parsedUrl = new URL(mapped.get('SUPABASE_DB_URL_LOCAL'));
      if (parsedUrl.password) {
        mapped.set('SUPABASE_DB_PASSWORD_LOCAL', parsedUrl.password);
      }
    } catch (error) {
      console.warn('[sync-supabase-env] Unable to parse database URL for password extraction:', error.message);
    }
  }
  return mapped;
}

function formatEnvValue(value) {
  if (value === '' || /[^A-Za-z0-9_./:@-]/.test(value)) {
    return JSON.stringify(value);
  }
  return value;
}

function parseExistingEnv(content) {
  const lines = content.split(/\r?\n/);
  return lines.map((line) => {
    const trimmed = line.trim();
    if (!trimmed) return { type: 'blank', raw: line };
    if (trimmed.startsWith('#')) return { type: 'comment', raw: line };
    const equalsIndex = line.indexOf('=');
    if (equalsIndex === -1) return { type: 'other', raw: line };
    const key = line.slice(0, equalsIndex).trim();
    const value = line.slice(equalsIndex + 1);
    return { type: 'entry', key, value, raw: line };
  });
}

function applyEnvUpdates(originalContent, updates) {
  const lines = parseExistingEnv(originalContent);
  const handledKeys = new Set();
  const updatedLines = lines.map((line) => {
    if (line.type === 'entry' && updates.has(line.key)) {
      handledKeys.add(line.key);
      const value = updates.get(line.key);
      return `${line.key}=${formatEnvValue(value)}`;
    }
    return line.raw;
  });

  const missingKeys = [];
  for (const [key, value] of updates) {
    if (!handledKeys.has(key)) {
      missingKeys.push([key, value]);
    }
  }

  if (missingKeys.length > 0) {
    if (updatedLines.length > 0 && updatedLines[updatedLines.length - 1].trim() !== '') {
      updatedLines.push('');
    }
    updatedLines.push('# Synced from Supabase CLI status');
    for (const [key, value] of missingKeys) {
      updatedLines.push(`${key}=${formatEnvValue(value)}`);
    }
  }

  return `${updatedLines.join('\n')}${updatedLines.length > 0 ? '\n' : ''}`;
}

async function ensureFileUpdated(filePath, updates) {
  try {
    await access(filePath, constants.F_OK);
    const existing = await readFile(filePath, 'utf8');
    const nextContent = applyEnvUpdates(existing, updates);
    if (nextContent === existing) {
      return { filePath, status: 'unchanged' };
    }
    await writeFile(filePath, nextContent, 'utf8');
    return { filePath, status: 'updated' };
  } catch (error) {
    if (error.code !== 'ENOENT') {
      throw error;
    }
    const header = [
      '# Generated Supabase environment variables',
      '# Run this script after `supabase start` to refresh.',
      ''
    ];
    const lines = [];
    for (const [key, value] of updates) {
      lines.push(`${key}=${formatEnvValue(value)}`);
    }
    const content = `${header.concat(lines).join('\n')}\n`;
    const dir = path.dirname(filePath);
    await mkdir(dir, { recursive: true });
    await writeFile(filePath, content, 'utf8');
    return { filePath, status: 'created' };
  }
}

async function readSupabaseStatus() {
  let output = '';
  try {
    const { stdout, stderr } = await execFileAsync('supabase', ['status'], {
      encoding: 'utf8',
      maxBuffer: 10 * 1024 * 1024
    });
    output = `${stdout}\n${stderr}`;
  } catch (error) {
    if (error.code === 'ENOENT') {
      console.error('[sync-supabase-env] Supabase CLI is not installed or not on PATH.');
      return null;
    }
    output = `${error.stdout ?? ''}\n${error.stderr ?? ''}`;
    if (!output.trim()) {
      console.error('[sync-supabase-env] Failed to run `supabase status`:', error.message || error);
      return null;
    }
  }
  return output;
}

function buildUpdateMap(rawOutput) {
  if (!rawOutput || !rawOutput.trim()) return null;
  const envStyle = parseEnvBlock(rawOutput);
  if (envStyle.size > 0) return mapStatusKeysToEnv(envStyle);
  const prettyValues = parsePrettyStatus(rawOutput);
  if (prettyValues.size > 0) return prettyValues;
  return null;
}

async function main() {
  const statusOutput = await readSupabaseStatus();
  if (!statusOutput) {
    process.exitCode = 1;
    return;
  }

  const updates = buildUpdateMap(statusOutput);
  if (!updates || updates.size === 0) {
    console.error('[sync-supabase-env] Unable to parse Supabase status output.');
    process.exitCode = 1;
    return;
  }

  preferNewAndBackfill(updates);

  if (!hasRequired(updates)) {
    const missing = [];
    if (!updates.has('NEXT_PUBLIC_SUPABASE_URL')) missing.push('NEXT_PUBLIC_SUPABASE_URL');
    if (!(updates.has('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY') || updates.has('NEXT_PUBLIC_SUPABASE_ANON_KEY'))) {
      missing.push('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY or NEXT_PUBLIC_SUPABASE_ANON_KEY');
    }
    console.error('[sync-supabase-env] Missing required keys:', missing.join(', '));
    process.exitCode = 1;
    return;
  }

  if (!(updates.has('SUPABASE_SECRET_KEY') || updates.has('SUPABASE_SERVICE_ROLE_KEY'))) {
    console.warn('[sync-supabase-env] No secret/service key detected — continuing without it.');
  }

  for (const targetFile of TARGET_FILES) {
    try {
      const result = await ensureFileUpdated(targetFile, updates);
      const statusLabel =
        result.status === 'created' ? 'Created' :
        result.status === 'updated' ? 'Updated' : 'No changes for';
      console.log(`[sync-supabase-env] ${statusLabel} ${result.filePath}`);
    } catch (error) {
      console.error(`[sync-supabase-env] Failed to update ${targetFile}:`, error.message || error);
      process.exitCode = 1;
    }
  }
}

main();
