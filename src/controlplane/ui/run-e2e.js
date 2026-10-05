import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const nodeModules = path.resolve(__dirname, 'node_modules');
const current = process.env.NODE_PATH || '';
const nodePath = current ? `${nodeModules}${path.delimiter}${current}` : nodeModules;

const cli = path.resolve(nodeModules, '@playwright', 'test', 'cli.js');
const result = spawnSync(process.execPath, [cli, 'test', ...process.argv.slice(2)], {
  stdio: 'inherit',
  env: {
    ...process.env,
    NODE_PATH: nodePath,
  },
});
process.exit(result.status ?? 1);