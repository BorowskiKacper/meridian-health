import { existsSync, mkdirSync, readlinkSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const appRoot = resolve(here, '..');

const candidates = [
  process.env.ATLAS_ROOT,
  resolve(appRoot, '../3d-anatomy-atlas'),
  '/tmp/3d-anatomy-atlas',
  resolve(appRoot, '../../tmp/3d-anatomy-atlas'),
].filter(Boolean);

const atlasRoot = candidates.find((dir) => existsSync(join(dir, 'packages/atlas/src/core/index.ts')));
if (!atlasRoot) {
  console.error('Could not find the Svitylo atlas checkout. Set ATLAS_ROOT to the cloned repository.');
  process.exit(1);
}

const threeCandidates = [
  join(atlasRoot, 'packages/atlas/node_modules/three'),
  join(atlasRoot, 'node_modules/three'),
];
const threeRoot = threeCandidates.find((dir) => existsSync(join(dir, 'package.json')));
if (!threeRoot) {
  console.error(`three.js is not installed in ${atlasRoot}. Run pnpm install there first.`);
  process.exit(1);
}

const dataRoot = join(atlasRoot, 'packages/data/releases/1.1.0');
if (!existsSync(join(dataRoot, 'manifest.json'))) {
  console.error(`Anatomy release 1.1.0 is missing at ${dataRoot}.`);
  process.exit(1);
}

function link(target, path) {
  mkdirSync(dirname(path), { recursive: true });
  if (existsSync(path)) {
    let current = '';
    try {
      current = readlinkSync(path);
    } catch {
      current = '';
    }
    if (current === target) return;
    rmSync(path, { recursive: true, force: true });
  }
  symlinkSync(target, path, process.platform === 'win32' ? 'junction' : undefined);
}

link(join(atlasRoot, 'packages/atlas'), join(appRoot, 'vendor/atlas'));
link(threeRoot, join(appRoot, 'vendor/three'));
link(dataRoot, join(appRoot, 'public/anatomy-data/1.1.0'));

writeFileSync(
  join(appRoot, '.atlas-root'),
  JSON.stringify({ atlasRoot, threeRoot, dataRoot }, null, 2) + '\n',
);
console.log(`Linked atlas at ${atlasRoot}`);
