import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { readChunkGlb } from '../../packages/tools/src/lib/glb-writer.js';
import { openings } from '../../packages/tools/src/lib/mesh-checks.js';

const release = new URL('../../packages/data/releases/1.1.0/', import.meta.url);
const manifest = JSON.parse(readFileSync(new URL('manifest.json', release), 'utf8'));

describe('hackathon mannequin assets', () => {
  it('omits hair geometry and retains unique owners for all picking IDs', () => {
    const hair = manifest.structures.find((s: { id: string }) => s.id === 'regions.pubic_hairs');
    expect(hair.meshes).toBeUndefined();
    expect(hair.gap.reason).toBe('excluded');
    for (const mesh of [5, 196, 197, 198, 199]) {
      expect(manifest.structures.filter((s: { meshes?: number[] }) => s.meshes?.includes(mesh))).toHaveLength(1);
    }
  });

  for (const quality of ['standard', 'economy']) {
    it(`${quality}: neutral surface is closed, nondegenerate, and outward-facing`, async () => {
      const { nodes, prims } = await readChunkGlb(readFileSync(new URL(`${quality}/regions/root.glb`, release)));
      const matrix = nodes[0]!.getWorldMatrix(), prim = prims[0]!;
      const positions = prim.getAttribute('POSITION')!, normals = prim.getAttribute('NORMAL')!;
      const ids = prim.getAttribute('_ID')!, indices = prim.getIndices()!.getArray()!;
      const soup: number[] = [], seen = new Set<number>();
      for (let i = 0; i < indices.length; i += 3) {
        const mesh = ids.getElement(indices[i]!, [])[0]!;
        if (![5, 196, 197, 198, 199].includes(mesh)) continue;
        seen.add(mesh);
        const vertices = [0, 1, 2].map(k => {
          const v = indices[i + k]!;
          expect(ids.getElement(v, [])[0]).toBe(mesh);
          const p = positions.getElement(v, []).map((x, axis) => x * matrix[axis * 5]! + matrix[axis + 12]!);
          expect(p.every(Number.isFinite)).toBe(true);
          // Physical envelope prevents the original hanging/protruding anatomy returning.
          expect(Math.abs(p[0]!)).toBeLessThan(.0551);
          expect(p[1]!).toBeGreaterThan(.7739);
          expect(p[1]!).toBeLessThan(.8841);
          expect(p[2]!).toBeLessThan(.1308);
          soup.push(...p);
          return p;
        });
        const [a, b, c] = vertices as [number[], number[], number[]];
        const u = b.map((x, k) => x - a[k]!), v = c.map((x, k) => x - a[k]!);
        const cross = [u[1]! * v[2]! - u[2]! * v[1]!, u[2]! * v[0]! - u[0]! * v[2]!, u[0]! * v[1]! - u[1]! * v[0]!];
        expect(Math.hypot(...cross)).toBeGreaterThan(1e-10);
        const normal = normals.getElement(indices[i]!, []);
        expect(cross.reduce((sum, x, k) => sum + x * normal[k]!, 0)).toBeGreaterThan(0);
      }
      expect([...seen].sort((a, b) => a - b)).toEqual([5, 196, 197, 198, 199]);
      expect(openings(soup)).toEqual([]);
    });
  }
});
