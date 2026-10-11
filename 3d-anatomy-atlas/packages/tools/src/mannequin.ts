/** Make the hackathon's 1.1.0 body surface a neutral mannequin.
 * Run from the atlas: pnpm --filter @svitylo-atlas/tools exec tsx --conditions=source src/mannequin.ts
 * This is a presentation edit, not an anatomical correction. Internal organs are untouched.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { canonicalJson } from '@authorod/svitylo-3d-anatomy-atlas/schema';
import { readChunkGlb, writeChunkGlb, type ChunkMesh } from './lib/glb-writer.js';
import { DATA_RELEASES, sha256 } from './lib/io.js';
import type { MeshData } from './lib/geometry.js';
import { coverageMarkdown } from './lib/release.js';

const dir = resolve(process.argv[2] ?? join(DATA_RELEASES, '1.1.0'));
const manifest = JSON.parse(readFileSync(join(dir, 'manifest.json'), 'utf8'));
const coverage = JSON.parse(readFileSync(join(dir, manifest.reports.coverage.path), 'utf8'));
const note = 'Hackathon mannequin: external genital and pubic-hair geometry replaced by a smooth neutral skin surface; internal anatomy unchanged.';
const chunk = manifest.chunks.find((c: { id: string }) => c.id === 'regions.root');
const sourceHashes = {
  standard: '8be80c9432cbaeffe2920e2a928d5b2a5a9bd7a50bea2548de6d63c7b002bcc1',
  economy: '24f68dbe2645d4fa856b6e77abb3e762acc759c53c4a0d451a8efe40a714b2c1',
};
const qualities = ['standard', 'economy'] as const;
const smooth = (low: number, high: number, value: number) => {
  const t = Math.max(0, Math.min(1, (value - low) / (high - low)));
  return t * t * (3 - 2 * t);
};
// Lift the small inner-thigh/perineal rim into the neutral crotch. Apply the same
// continuous field to every adjoining region so their shared boundaries stay aligned.
function lift([x, y, z]: number[]): number {
  return .034 * (1 - smooth(.02, .065, Math.abs(x!))) * smooth(.70, .75, y!) *
    (1 - smooth(.77, .83, y!)) * smooth(-.005, .015, z!) * (1 - smooth(.095, .135, z!));
}
if (!chunk || manifest.version !== '1.1.0') throw new Error('Expected the 1.1.0 regions release.');
if (coverage.notes.includes(note)) {
  for (const q of qualities) {
    if (sha256(readFileSync(join(dir, chunk.files[q].path))) !== chunk.files[q].sha256) {
      throw new Error(`Edited ${q} asset does not match its manifest.`);
    }
  }
  console.log('Mannequin edit already applied.');
  process.exit(0);
}
// Fail before writing anything if a different source release is supplied.
for (const q of qualities) {
  if (sha256(readFileSync(join(dir, chunk.files[q].path))) !== sourceHashes[q]) {
    throw new Error(`Unexpected ${q} source geometry; inspect it before changing the patch dimensions.`);
  }
}

/** Closed, sheared ellipsoid in atlas metres, fitted between abdomen and inner thighs.
 * Shared positions and analytic normals across all three partitions prevent seams.
 * Mesh 5 becomes the upper neutral surface; 196–199 retain perineal picking.
 */
function neutralSurface(rings: number, segments: number, palette: number): ChunkMesh[] {
  const positions: number[][] = [], normals: number[][] = [], triangles: number[][] = [];
  for (let r = 0; r <= rings; r++) {
    const theta = Math.PI * r / rings;
    const count = r === 0 || r === rings ? 1 : segments;
    for (let s = 0; s < count; s++) {
      const phi = 2 * Math.PI * s / segments;
      const x = Math.sin(theta) * Math.cos(phi), y = Math.cos(theta), z = Math.sin(theta) * Math.sin(phi);
      positions.push([x * .055, .829 + y * .055, .055 + y * .037 + z * .066]);
      // Inverse-transpose of the scale/shear used for positions.
      const n = [x / .055, y / .055 - .037 * z / (.055 * .066), z / .066];
      const length = Math.hypot(...n);
      normals.push(n.map(v => v / length));
    }
  }
  const vertex = (r: number, s: number) => r === 0 ? 0 : r === rings ? positions.length - 1 : 1 + (r - 1) * segments + s % segments;
  for (let r = 0; r < rings; r++) for (let s = 0; s < segments; s++) {
    const a = vertex(r, s), b = vertex(r + 1, s), c = vertex(r + 1, s + 1), d = vertex(r, s + 1);
    if (a !== d) triangles.push([a, d, b]);
    if (b !== c) triangles.push([d, c, b]);
  }
  return [5, 196, 197, 198, 199].map(meshIndex => {
    const remap = new Map<number, number>(), p: number[] = [], n: number[] = [], indices: number[] = [];
    for (const tri of triangles) {
      const center = [0, 1, 2].map(k => tri.reduce((sum, v) => sum + positions[v]![k]!, 0) / 3);
      const owner = center[1]! > .845 ? 5 : center[2]! < .035 ? (center[0]! >= 0 ? 196 : 197) : (center[0]! >= 0 ? 198 : 199);
      if (owner !== meshIndex) continue;
      for (const v of tri) {
        if (!remap.has(v)) { remap.set(v, remap.size); p.push(...positions[v]!); n.push(...normals[v]!); }
        indices.push(remap.get(v)!);
      }
    }
    return { meshIndex, mesh: { positions: new Float32Array(p), normals: new Float32Array(n),
      indices: new Uint32Array(indices), materials: new Uint8Array(p.length / 3).fill(palette) } };
  });
}

const output = new Map<string, Uint8Array>();
for (const q of qualities) {
  const { nodes, prims } = await readChunkGlb(readFileSync(join(dir, chunk.files[q].path)));
  const node = nodes[0]!, prim = prims[0]!, matrix = node.getWorldMatrix();
  const position = prim.getAttribute('POSITION')!, normal = prim.getAttribute('NORMAL')!;
  const ids = prim.getAttribute('_ID')!, indices = prim.getIndices()!.getArray()!;
  const meshes: ChunkMesh[] = [];
  const perMesh = new Map<number, { vertices: number[]; indices: number[]; remap: Map<number, number> }>();
  for (let v = 0; v < position.getCount(); v++) {
    const id = ids.getElement(v, [])[0]!;
    let data = perMesh.get(id);
    if (!data) { data = { vertices: [], indices: [], remap: new Map() }; perMesh.set(id, data); }
    data.remap.set(v, data.vertices.length); data.vertices.push(v);
  }
  for (const v of indices) {
    const data = perMesh.get(ids.getElement(v, [])[0]!)!;
    data.indices.push(data.remap.get(v)!);
  }
  // Existing chunk writer uses uniform quantisation scale and no rotation.
  if (matrix[0] !== matrix[5] || matrix[0] !== matrix[10] || matrix[1] || matrix[2] || matrix[4] || matrix[6] || matrix[8] || matrix[9]) {
    throw new Error('Unexpected source transform.');
  }
  const skinPalette = ids.getElement(perMesh.get(198)!.vertices[0]!, [])[1]!;
  for (const [meshIndex, data] of perMesh) {
    if ([5, 196, 197, 198, 199].includes(meshIndex)) continue;
    const p: number[] = [], n: number[] = [], materials: number[] = [];
    for (const v of data.vertices) {
      const point = position.getElement(v, []);
      const world = point.map((value, k) => value * matrix[k * 5]! + matrix[k + 12]!);
      const amount = lift(world), originalNormal = normal.getElement(v, []);
      if (amount > 0) {
        // Inverse-transpose Jacobian of the local deformation, preserving smooth shading.
        const h = 1e-5;
        const derivative = world.map((_, axis) => {
          const plus = [...world], minus = [...world]; plus[axis]! += h; minus[axis]! -= h;
          return (lift(plus) - lift(minus)) / (2 * h);
        });
        const ny = originalNormal[1]! / (1 + derivative[1]!);
        const warped = [originalNormal[0]! - ny * derivative[0]!, ny, originalNormal[2]! - ny * derivative[2]!];
        const length = Math.hypot(...warped);
        n.push(...warped.map(value => value / length));
      } else n.push(...originalNormal);
      world[1]! += amount; p.push(...world); materials.push(ids.getElement(v, [])[1]!);
    }
    const mesh: MeshData = { positions: new Float32Array(p), normals: new Float32Array(n), materials: new Uint8Array(materials), indices: new Uint32Array(data.indices) };
    meshes.push({ meshIndex, mesh });
  }
  meshes.push(...neutralSurface(q === 'standard' ? 32 : 16, q === 'standard' ? 64 : 32, skinPalette));
  meshes.sort((a, b) => a.meshIndex - b.meshIndex);
  const written = await writeChunkGlb(node.getName(), meshes, node.getExtras());
  const old = chunk.files[q];
  coverage.totals.triangles[q] += written.triangles - old.triangles;
  coverage.totals.bytes[q] += written.bytes.length - old.bytes;
  const system = coverage.systems.find((s: { id: string }) => s.id === 'regions');
  system[q === 'standard' ? 'trianglesStandard' : 'trianglesEconomy'] = written.triangles;
  chunk.files[q] = { path: old.path, bytes: written.bytes.length, sha256: sha256(written.bytes), triangles: written.triangles, vertices: written.vertices };
  output.set(old.path, written.bytes);
  console.log(`${q}: ${old.triangles} -> ${written.triangles} triangles`);
}

// Retain every numeric mesh ID without leaving a selectable hair surface or orphan ID.
const hair = manifest.structures.find((s: { id: string }) => s.id === 'regions.pubic_hairs');
delete hair.meshes;
hair.gap = { reason: 'excluded', note: { en: 'Omitted for the hackathon mannequin presentation.' } };
const perineum = manifest.structures.find((s: { id: string }) => s.id === 'regions.regions_of_perineum');
perineum.meshes = [5];
perineum.asset = hair.asset;
perineum.review.notes = note;
for (const id of ['regions.anal_region_l', 'regions.anal_region_r', 'regions.urogenital_region_l', 'regions.urogenital_region_r']) {
  manifest.structures.find((s: { id: string }) => s.id === id).review.notes = note;
}
coverage.notes.push(note);
coverage.gaps.push({ id: hair.id, reason: 'excluded' });
coverage.totals.gaps++;
coverage.systems.find((s: { id: string }) => s.id === 'regions').gaps++;
const coverageBytes = Buffer.from(JSON.stringify(coverage, null, 2) + '\n');
output.set(manifest.reports.coverage.path, coverageBytes);
output.set('reports/COVERAGE.md', Buffer.from(coverageMarkdown(coverage)));
manifest.reports.coverage.bytes = coverageBytes.length;
manifest.reports.coverage.sha256 = sha256(coverageBytes);
const { contentHash: _, ...body } = manifest;
manifest.contentHash = sha256(canonicalJson(body));
output.set('manifest.json', Buffer.from(JSON.stringify(manifest) + '\n'));
const sums = readFileSync(join(dir, 'SHA256SUMS'), 'utf8').split('\n').map(line => {
  const path = line.slice(66), bytes = output.get(path);
  return bytes ? `${sha256(bytes)}  ${path}` : line;
}).join('\n');
// All decoding and metadata preparation succeeds before committing the outputs.
for (const [path, bytes] of output) writeFileSync(join(dir, path), bytes);
writeFileSync(join(dir, 'SHA256SUMS'), sums);
