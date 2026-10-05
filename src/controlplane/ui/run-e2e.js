import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const nodeModules = path.resolve(__dirname, 'node_modules');
const current = process.env.NODE_PATH || '';
const nodePath = current ? `${nodeModules}${path.delimiter}${current}` : nodeModules;

const args = process.argv.slice(2);
const normalizedArgs = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--grep' && i + 1 < args.length) {
    normalizedArgs.push(`--grep=${args[i + 1]}`);
    i++;
  } else if (!args[i].startsWith('-') && args[i].includes('|')) {
    normalizedArgs.push(`--grep=${args[i]}`);
  } else {
    normalizedArgs.push(args[i]);
  }
}

const cli = path.resolve(nodeModules, '@playwright', 'test', 'cli.js');
const result = spawnSync(process.execPath, [cli, 'test', ...normalizedArgs], {
  stdio: 'inherit',
  env: {
    ...process.env,
    NODE_PATH: nodePath,
  },
});
process.exit(result.status ?? 1);
