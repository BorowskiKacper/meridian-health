import {
  ConeGeometry,
  CylinderGeometry,
  DoubleSide,
  Group,
  Mesh,
  MeshBasicMaterial,
  PlaneGeometry,
  SphereGeometry,
  TorusGeometry,
  Vector3,
} from 'three';

const up = new Vector3(0, 1, 0);

export function alignUp(group: Group, outward: Vector3): void {
  const direction = outward.clone();
  if (direction.lengthSq() < 1e-8) direction.set(0, 1, 0);
  group.quaternion.setFromUnitVectors(up, direction.normalize());
}

export function makePin(color: string): Group {
  const group = new Group();
  const solid = new MeshBasicMaterial({ color });
  const head = new Mesh(new SphereGeometry(0.0065, 22, 16), solid);
  const stem = new Mesh(new CylinderGeometry(0.00115, 0.00115, 0.038, 8), solid);
  stem.position.y = 0.022;
  const ringMaterial = new MeshBasicMaterial({ color, transparent: true, opacity: 0.95, depthTest: false });
  const ring = new Mesh(new TorusGeometry(0.015, 0.00135, 8, 32), ringMaterial);
  ring.rotation.x = Math.PI / 2;
  ring.name = 'ring';
  ring.renderOrder = 3;
  const tip = new Group();
  tip.name = 'tip';
  tip.position.y = 0.046;
  group.add(head, stem, ring, tip);
  return group;
}

export function makeImpact(color: string): Group {
  const group = new Group();
  group.name = 'impact';
  const material = new MeshBasicMaterial({ color, transparent: true, opacity: 0.95, depthTest: false });
  const shaft = new Mesh(new CylinderGeometry(0.0028, 0.0028, 0.16, 12), material);
  shaft.position.y = 0.12;
  const head = new Mesh(new ConeGeometry(0.011, 0.036, 16), material);
  head.position.y = 0.034;
  head.rotation.x = Math.PI;
  shaft.renderOrder = 4;
  head.renderOrder = 4;
  group.add(shaft, head);
  return group;
}

export function makeSegment(a: Vector3, b: Vector3, color: string, radius = 0.0018): Group {
  const group = new Group();
  const material = new MeshBasicMaterial({ color, depthTest: false });
  const direction = new Vector3().subVectors(b, a);
  const length = Math.max(direction.length(), 0.0001);
  const shaft = new Mesh(new CylinderGeometry(radius, radius, length, 8), material);
  shaft.position.copy(a).addScaledVector(direction, 0.5);
  shaft.quaternion.setFromUnitVectors(up, direction.normalize());
  shaft.renderOrder = 4;
  const cap = (point: Vector3) => {
    const mesh = new Mesh(new SphereGeometry(radius * 2.4, 14, 12), material);
    mesh.position.copy(point);
    mesh.renderOrder = 4;
    return mesh;
  };
  group.add(shaft, cap(a), cap(b));
  return group;
}

export function makeCutPlane(span: number): Group {
  const group = new Group();
  const sheet = new Mesh(
    new PlaneGeometry(span, span),
    new MeshBasicMaterial({
      color: '#c5d4ea',
      transparent: true,
      opacity: 0.16,
      side: DoubleSide,
      depthWrite: false,
    }),
  );
  sheet.renderOrder = 2;
  const handle = new Mesh(
    new SphereGeometry(Math.max(0.012, span * 0.012), 18, 14),
    new MeshBasicMaterial({ color: '#f4f7fb', depthTest: false }),
  );
  handle.name = 'handle';
  handle.position.set(span * 0.42, 0, 0.01);
  handle.renderOrder = 5;
  group.add(sheet, handle);
  return group;
}

export function makeCursor(): Mesh {
  const mesh = new Mesh(
    new SphereGeometry(0.0045, 16, 12),
    new MeshBasicMaterial({ color: '#f7f4ee', transparent: true, opacity: 0.95, depthTest: false }),
  );
  mesh.renderOrder = 6;
  mesh.visible = false;
  return mesh;
}
