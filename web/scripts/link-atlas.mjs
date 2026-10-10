import { existsSync, mkdirSync, readlinkSync, realpathSync, rmSync, symlinkSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const appRoot = resolve(here, "..");

const candidates = [process.env.ATLAS_ROOT, resolve(appRoot, "../3d-anatomy-atlas")].filter(Boolean);
const atlasRoot = candidates.find((dir) => existsSync(join(dir, "packages/atlas/src/core/index.ts")));
if (!atlasRoot) {
  console.error("Could not find the Svitylo atlas checkout. Set ATLAS_ROOT to the cloned repository.");
  process.exit(1);
}

const threeRoot = [join(atlasRoot, "packages/atlas/node_modules/three"), join(atlasRoot, "node_modules/three")].find(
  (dir) => existsSync(join(dir, "package.json")),
);
if (!threeRoot) {
  console.error(`three.js is not installed in ${atlasRoot}. Run pnpm install there first.`);
  process.exit(1);
}

const dataRoot = join(atlasRoot, "packages/data/releases/1.1.0");
if (!existsSync(join(dataRoot, "manifest.json"))) {
  console.error(`Anatomy release 1.1.0 is missing at ${dataRoot}.`);
  process.exit(1);
}

function link(target, path) {
  mkdirSync(dirname(path), { recursive: true });
  if (existsSync(path)) {
    let current = "";
    try {
      current = readlinkSync(path);
    } catch {
      current = "";
    }
    if (resolve(current) === resolve(target)) return;
    rmSync(path, { recursive: true, force: true });
  }
  symlinkSync(target, path, process.platform === "win32" ? "junction" : undefined);
}

// The atlas and the overlay must share one copy of three, so link its real path rather than pnpm's junction.
link(join(atlasRoot, "packages/atlas"), join(appRoot, "vendor/atlas"));
link(realpathSync(threeRoot), join(appRoot, "vendor/three"));
link(dataRoot, join(appRoot, "public/anatomy-data/1.1.0"));
console.log(`Linked atlas at ${atlasRoot}`);
