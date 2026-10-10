import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

const appRoot = fileURLToPath(new URL('.', import.meta.url));

function roots(): { atlasRoot: string; threeRoot: string } {
  const stamp = join(appRoot, '.atlas-root');
  if (existsSync(stamp)) return JSON.parse(readFileSync(stamp, 'utf8')) as { atlasRoot: string; threeRoot: string };
  const atlasRoot = ['/tmp/3d-anatomy-atlas', resolve(appRoot, '../3d-anatomy-atlas')].find((dir) =>
    existsSync(join(dir, 'packages/atlas/src/core/index.ts')),
  );
  if (!atlasRoot) throw new Error('Atlas checkout not found. Run npm run link.');
  const threeRoot = [join(atlasRoot, 'packages/atlas/node_modules/three'), join(atlasRoot, 'node_modules/three')].find((dir) =>
    existsSync(join(dir, 'package.json')),
  );
  if (!threeRoot) throw new Error('three.js missing from the atlas checkout.');
  return { atlasRoot, threeRoot };
}

const { atlasRoot, threeRoot } = roots();

export default defineConfig({
  resolve: {
    alias: [
      {
        find: '@authorod/svitylo-3d-anatomy-atlas/core',
        replacement: join(atlasRoot, 'packages/atlas/src/core/index.ts'),
      },
      {
        find: /^three\/addons\/(.*)/,
        replacement: `${join(threeRoot, 'examples/jsm')}/$1`,
      },
      { find: 'three', replacement: threeRoot },
    ],
    dedupe: ['three'],
  },
  server: {
    host: '127.0.0.1',
    port: 43131,
    strictPort: true,
    fs: { allow: [appRoot, atlasRoot, threeRoot] },
    watch: { ignored: ['**/public/anatomy-data/**', '**/vendor/**'] },
  },
});
