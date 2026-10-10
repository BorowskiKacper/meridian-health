import { Ray, Vector3, type Box3, type Scene } from 'three';
import type { AtlasViewer } from '@authorod/svitylo-3d-anatomy-atlas/core';
import { meshBounds, rayCrossings } from '@atlas/core/render/picking';
import type { ChunkGeometry } from '@atlas/core/render/chunk-geometry';
import type { CameraRig } from '@atlas/core/render/camera-rig';

export interface LiveRenderer {
  scene: Scene;
  canvas: HTMLCanvasElement;
  rig: CameraRig;
  requestRender: () => void;
  pick: (clientX: number, clientY: number, pickable: (mesh: number) => boolean) => { mesh: number; point: Vector3 } | null;
  chunk: (chunk: number) => ChunkGeometry | undefined;
}

export function liveRenderer(viewer: AtlasViewer): LiveRenderer | null {
  return (viewer as unknown as { renderer: LiveRenderer | null }).renderer;
}

function chunkOf(viewer: AtlasViewer, renderer: LiveRenderer) {
  const chunks = viewer.catalog.index.meshChunk;
  return (mesh: number): ChunkGeometry | undefined => {
    const index = chunks[mesh] ?? -1;
    return index < 0 ? undefined : renderer.chunk(index);
  };
}

export function structureMeshes(viewer: AtlasViewer, id: string): number[] {
  const index = viewer.catalog.index;
  const { units } = index.expand([id], 'all');
  const meshes: number[] = [];
  for (const unit of units) {
    const structure = index.structures[unit];
    if (structure) meshes.push(...structure.meshes);
  }
  return meshes;
}

export function structureBounds(viewer: AtlasViewer, id: string): Box3 | null {
  const renderer = liveRenderer(viewer);
  if (!renderer) return null;
  const box = meshBounds(structureMeshes(viewer, id), chunkOf(viewer, renderer));
  return box.isEmpty() ? null : box;
}

/**
 * A point on the structure's surface, just outside the mesh, reached by a ray from
 * `outward`. Falls back to the bounding-box centre when the ray misses.
 */
export function surfaceAnchor(viewer: AtlasViewer, id: string, outward: Vector3): { point: Vector3; normal: Vector3 } | null {
  const renderer = liveRenderer(viewer);
  const box = structureBounds(viewer, id);
  if (!renderer || !box) return null;
  const center = box.getCenter(new Vector3());
  const reach = box.getSize(new Vector3()).length() + 0.05;
  const own = new Set(structureMeshes(viewer, id));
  const chunks = [...renderer.scene.children]
    .map((child) => {
      const name = child.name;
      if (!name.startsWith('chunk-')) return undefined;
      return renderer.chunk(Number(name.slice(6)));
    })
    .filter((chunk): chunk is ChunkGeometry => Boolean(chunk));

  const attempts = [
    outward.clone(),
    new Vector3(0, 0, 1),
    new Vector3(1, 0, 0.4),
    new Vector3(-1, 0, 0.4),
    new Vector3(0, 1, 0.2),
    new Vector3(0, -1, 0.2),
  ];
  for (const attempt of attempts) {
    if (attempt.lengthSq() < 1e-8) continue;
    const normal = attempt.normalize();
    const origin = center.clone().addScaledVector(normal, reach);
    const direction = center.clone().sub(origin).normalize();
    const hits = rayCrossings(new Ray(origin, direction), chunks, (mesh) => own.has(mesh));
    if (!hits.length) continue;
    hits.sort((a, b) => a.distance - b.distance);
    const point = origin.clone().addScaledVector(direction, hits[0]!.distance).addScaledVector(normal, 0.0035);
    return { point, normal };
  }
  return { point: center, normal: outward.clone().normalize() };
}

export function structureCenters(viewer: AtlasViewer): Map<string, Vector3> {
  const renderer = liveRenderer(viewer);
  const centers = new Map<string, Vector3>();
  if (!renderer) return centers;
  const index = viewer.catalog.index;
  const ofMesh = chunkOf(viewer, renderer);
  for (const structure of index.structures) {
    if (!structure.meshes.length) continue;
    const box = meshBounds(structure.meshes, ofMesh);
    if (!box.isEmpty()) centers.set(structure.id, box.getCenter(new Vector3()));
  }
  return centers;
}

export function protectedIds(viewer: AtlasViewer, ids: string[]): Set<string> {
  const index = viewer.catalog.index;
  const kept = new Set<string>();
  const { units } = index.expand(ids, 'all');
  for (const unit of units) {
    const structure = index.structures[unit];
    if (structure) kept.add(structure.id);
  }
  return kept;
}

export function nameOfMesh(viewer: AtlasViewer, mesh: number): string | null {
  const owner = viewer.catalog.index.meshOwner[mesh] ?? -1;
  if (owner < 0) return null;
  const structure = viewer.catalog.index.structures[owner];
  return structure ? viewer.catalog.names.label(structure.id, 'en') : null;
}

export function meshVisible(viewer: AtlasViewer, mesh: number): boolean {
  const modes = (viewer as unknown as { meshModes?: Uint8Array }).meshModes;
  if (!modes) return true;
  return (modes[mesh] ?? 0) !== 0;
}
