"use client";

import { useEffect, useRef, useState } from "react";
import { bodyContext } from "@/lib/data";
import type { BodyScene } from "./scene/controller";
import { initialSnapshot, type SceneFinding, type SceneSnapshot } from "./scene/types";

/** Boots the atlas on the client only; three.js and the overlay never load during server rendering. */
export function useBodyScene(findings: SceneFinding[]) {
  const viewRef = useRef<HTMLDivElement>(null);
  const labelsRef = useRef<HTMLDivElement>(null);
  const findingsRef = useRef(findings);
  const [scene, setScene] = useState<BodyScene | null>(null);
  const [snapshot, setSnapshot] = useState<SceneSnapshot>(initialSnapshot);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    findingsRef.current = findings;
  }, [findings]);

  useEffect(() => {
    let live = true;
    let instance: BodyScene | null = null;
    void import("./scene/controller").then(({ BodyScene }) => {
      const view = viewRef.current;
      const labels = labelsRef.current;
      if (!live || !view || !labels) return;
      instance = new BodyScene(view, labels, setSnapshot);
      setScene(instance);
      void instance.boot(bodyContext, findingsRef.current);
    });
    return () => {
      live = false;
      instance?.dispose();
    };
  }, [attempt]);

  const key = findings.map((f) => f.id).join("|");
  useEffect(() => {
    void scene?.setFindings(findingsRef.current);
  }, [scene, key]);

  return { viewRef, labelsRef, scene, snapshot, retry: () => setAttempt((n) => n + 1) };
}
