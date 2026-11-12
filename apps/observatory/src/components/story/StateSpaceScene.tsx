"use client";

import { Line } from "@react-three/drei";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import type { MotionValue } from "motion/react";
import * as THREE from "three";
import { inverseIllustration } from "@/lib/inverse";
import { buildSceneData, type Assessment, type V3 } from "@/lib/scene-data";
import { sceneState, type Layer, type SceneState } from "@/lib/story";

export interface UserView {
  dAz: number;
  dEl: number;
  zoom: number;
}

export type FocusLayer = "C" | "E" | "Y" | "boundary" | null;

export interface SceneProps {
  position: MotionValue<number>;
  userView: React.RefObject<UserView>;
  focus: FocusLayer;
  lowEnd: boolean;
  reducedMotion: boolean;
  active: boolean;
  onReady?: (invalidate: () => void) => void;
  onHover?: (a: Assessment | null) => void;
}

/* Mark colours: the validated night palette (see globals.css). */
const COLORS = { C: "#1fa0a8", E: "#d27a2a", Y: "#8a77e0", boundary: "#de5a52", grid: "#2a303b", axis: "#6b7385", band: "#8a77e0" };

/** Which focus button keeps which scene layers bright. */
const FOCUS_KEEP: Record<Exclude<FocusLayer, null>, Layer[]> = {
  C: ["C", "candidates", "gap"],
  E: ["E", "gap", "residual"],
  Y: ["Y", "band", "residual"],
  boundary: ["boundary", "future"],
};

function weight(st: SceneState, layer: Layer, focus: FocusLayer): number {
  const w = st.layers[layer];
  if (!focus) return w;
  return FOCUS_KEEP[focus].includes(layer) ? Math.max(w, 0.35) : w * 0.12;
}

type Line2Like = THREE.Object3D & { material: { opacity: number; transparent: boolean }; geometry: THREE.InstancedBufferGeometry };

function Rig({ position, userView, lowEnd, reducedMotion }: Pick<SceneProps, "position" | "userView" | "lowEnd" | "reducedMotion">) {
  const { camera, invalidate } = useThree();
  const cur = useRef({ az: 0, el: 0, r: 0, tx: 0, ty: 0, tz: 0, init: false });
  const look = useMemo(() => new THREE.Vector3(), []);
  useEffect(() => position.on("change", () => invalidate()), [position, invalidate]);
  useFrame((_, delta) => {
    const pose = sceneState(position.get()).pose;
    const u = userView.current;
    const target = { az: pose.az + u.dAz, el: Math.min(1.3, Math.max(-0.15, pose.el + u.dEl)), r: pose.r * u.zoom, tx: pose.tx, ty: pose.ty, tz: pose.tz };
    const c = cur.current;
    if (!c.init || reducedMotion) Object.assign(c, target, { init: true });
    const k = 1 - Math.exp(-Math.min(delta, 0.1) * (lowEnd ? 10 : 7));
    let moving = false;
    for (const key of ["az", "el", "r", "tx", "ty", "tz"] as const) {
      const diff = target[key] - c[key];
      if (Math.abs(diff) > 1e-3) {
        c[key] += diff * k;
        moving = true;
      } else c[key] = target[key];
    }
    camera.position.set(c.tx + c.r * Math.cos(c.el) * Math.sin(c.az), c.ty + c.r * Math.sin(c.el), c.tz + c.r * Math.cos(c.el) * Math.cos(c.az));
    look.set(c.tx, c.ty, c.tz);
    camera.lookAt(look);
    if (moving) invalidate();
  });
  return null;
}

type Slot<T> = { node: T | null };
const slot = <T,>(): Slot<T> => ({ node: null });

function makeContext(lowEnd: boolean, data: ReturnType<typeof buildSceneData>, accepted: number) {
  return {
    lines: {} as Record<string, Line2Like | null>,
    labels: {} as Record<string, HTMLDivElement>,
    labelDefs: [
      ["C", data.anchors.C, "C · latent capacity", ""],
      ["E", data.anchors.E, "E · expressed performance", ""],
      ["Y", data.anchors.Y, "Y · 32 noisy assessments", ""],
      ["S", data.anchors.S, "depth: suppression S", "scene-label-axis"],
      ["boundary", data.anchors.boundary, "history ends day 223 · forecasts from 224", ""],
      ["cand", data.anchors.candidates, `${accepted} settings fit as well`, ""],
      ["time", data.anchors.time, "time →", "scene-label-axis"],
    ] as [string, V3, string, string][],
    yMesh: slot<THREE.InstancedMesh>(),
    yfMesh: slot<THREE.InstancedMesh>(),
    plane: slot<THREE.Mesh>(),
    hover: slot<THREE.Mesh>(),
    mats: {
      y: new THREE.MeshBasicMaterial({ color: COLORS.Y, transparent: true }),
      yf: new THREE.MeshBasicMaterial({ color: COLORS.Y, transparent: true, wireframe: true }),
      plane: new THREE.MeshBasicMaterial({ color: COLORS.boundary, transparent: true, side: THREE.DoubleSide, depthWrite: false }),
      hover: new THREE.MeshBasicMaterial({ color: "#ffffff" }),
    },
    sphere: new THREE.SphereGeometry(0.075, lowEnd ? 8 : 14, lowEnd ? 6 : 10),
    tmp: new THREE.Vector3(),
  };
}
type Ctx = ReturnType<typeof makeContext>;

const bindSlot =
  <T,>(s: Slot<T>) =>
  (n: T | null) => {
    s.node = n;
  };

const bindLine = (ctx: Ctx, key: string, segments: number) => (n: unknown) => {
  const ln = n as Line2Like | null;
  if (ln) {
    ln.userData.segments = segments;
    ln.material.transparent = true;
  }
  ctx.lines[key] = ln;
};

function placeInstances(ctx: Ctx, data: ReturnType<typeof buildSceneData>) {
  const m = new THREE.Matrix4();
  const y = ctx.yMesh.node;
  const yf = ctx.yfMesh.node;
  data.y.forEach((p, i) => y?.setMatrixAt(i, m.makeTranslation(p[0], p[1], p[2])));
  data.yFuture.forEach((p, i) => yf?.setMatrixAt(i, m.compose(new THREE.Vector3(...p), new THREE.Quaternion(), new THREE.Vector3(1.5, 1.5, 1.5))));
  if (y) y.instanceMatrix.needsUpdate = true;
  if (yf) yf.instanceMatrix.needsUpdate = true;
}

/** Labels are plain DOM nodes in one overlay layer, projected from 3D anchors in the same frame as the camera. */
function mountLabels(ctx: Ctx, host: HTMLElement): () => void {
  const layer = document.createElement("div");
  layer.className = "scene-labels";
  layer.setAttribute("aria-hidden", "true");
  for (const [key, , text, cls] of ctx.labelDefs) {
    const el = document.createElement("div");
    el.className = `scene-label ${cls}`.trim();
    el.textContent = text;
    el.style.opacity = "0";
    layer.appendChild(el);
    ctx.labels[key] = el;
  }
  host.appendChild(layer);
  return () => {
    layer.remove();
    ctx.labels = {};
  };
}

function frame(ctx: Ctx, p: number, focus: FocusLayer, accepted: number, camera: THREE.Camera, size: { width: number; height: number }) {
  const st = sceneState(p);
  const set = (key: string, layer: Layer, scale = 1) => {
    const ln = ctx.lines[key];
    if (!ln) return;
    const o = weight(st, layer, focus) * scale;
    ln.material.opacity = o;
    ln.visible = o > 0.01;
    const count = (ln.userData.segments as number | undefined) ?? Infinity;
    ln.geometry.instanceCount = Math.max(0, Math.ceil(count * st.draw[layer]));
  };
  set("C", "C");
  set("E", "E");
  set("gap", "gap", 0.8);
  set("residual", "residual", 0.9);
  set("band", "band", 0.55);
  set("boundaryLine", "boundary");
  set("cCont", "future", 0.9);
  set("cCess", "future", 0.9);
  set("eCont", "future", 0.9);
  for (let i = 0; i < accepted; i += 1) {
    if (!ctx.lines[`candC${i}`]) break;
    set(`candC${i}`, "candidates", 0.7);
    set(`candE${i}`, "candidates", 0.28);
  }
  ctx.mats.y.opacity = weight(st, "Y", focus);
  ctx.mats.yf.opacity = weight(st, "future", focus);
  ctx.mats.plane.opacity = 0.14 * weight(st, "boundary", focus);
  if (ctx.yMesh.node) ctx.yMesh.node.visible = ctx.mats.y.opacity > 0.01;
  if (ctx.yfMesh.node) ctx.yfMesh.node.visible = ctx.mats.yf.opacity > 0.01;
  if (ctx.plane.node) ctx.plane.node.visible = ctx.mats.plane.opacity > 0.002;
  for (const [key, pos] of ctx.labelDefs) {
    const el = ctx.labels[key];
    if (!el) continue;
    ctx.tmp.set(pos[0], pos[1], pos[2]).project(camera);
    el.style.transform = `translate(-50%, -50%) translate(${((ctx.tmp.x + 1) / 2) * size.width}px, ${((1 - ctx.tmp.y) / 2) * size.height}px)`;
    el.style.visibility = ctx.tmp.z > 1 ? "hidden" : "visible";
  }
  const lab = (key: string, o: number) => {
    const el = ctx.labels[key];
    if (el) el.style.opacity = String(o > 0.5 ? Math.min(1, (o - 0.5) * 2) : 0);
  };
  lab("C", weight(st, "C", focus) * st.draw.C);
  lab("E", weight(st, "E", focus) * st.draw.E);
  lab("Y", st.layers.C < 0.2 ? weight(st, "Y", focus) : 0);
  lab("S", st.layers.gap);
  lab("boundary", weight(st, "boundary", focus));
  lab("cand", weight(st, "candidates", focus) * st.draw.candidates);
  lab("time", st.act <= 1 ? 1 : 0);
}

function setHover(ctx: Ctx, p: V3 | undefined) {
  const h = ctx.hover.node;
  if (!h) return;
  if (p) h.position.set(p[0], p[1], p[2]);
  h.visible = Boolean(p);
}

function Scene({ position, focus, lowEnd, active, onHover }: Pick<SceneProps, "position" | "focus" | "lowEnd" | "active" | "onHover">) {
  const { invalidate, gl, camera, size } = useThree();
  const data = useMemo(() => buildSceneData(lowEnd ? 4 : 2), [lowEnd]);
  const inv = useMemo(() => inverseIllustration(), []);
  const ctx = useMemo(() => makeContext(lowEnd, data, inv.accepted), [lowEnd, data, inv]);

  useEffect(() => {
    placeInstances(ctx, data);
    invalidate();
  }, [ctx, data, invalidate]);
  useEffect(() => {
    const host = gl.domElement.parentElement;
    if (!host) return;
    const unmount = mountLabels(ctx, host);
    invalidate();
    return unmount;
  }, [ctx, gl, invalidate]);
  useEffect(() => invalidate(), [focus, active, invalidate]);
  useFrame(() => frame(ctx, position.get(), focus, inv.shown.length, camera, size));

  function hover(e: ThreeEvent<PointerEvent>) {
    const id = e.instanceId;
    if (id === undefined || sceneState(position.get()).layers.Y < 0.3) return;
    e.stopPropagation();
    setHover(ctx, data.y[id]);
    onHover?.(data.yInfo[id] ?? null);
    invalidate();
  }
  function unhover() {
    setHover(ctx, undefined);
    onHover?.(null);
    invalidate();
  }

  const dash = { dashed: true, dashSize: 0.18, gapSize: 0.12 } as const;
  return (
    <group>
      <Line points={data.grid} segments color={COLORS.grid} lineWidth={0.6} transparent opacity={0.6} />
      <Line points={data.axes.x} color={COLORS.axis} lineWidth={1.1} />
      <Line points={data.axes.y} color={COLORS.axis} lineWidth={1.1} />
      <Line points={data.axes.z} color={COLORS.axis} lineWidth={1.1} />

      <Line ref={bindLine(ctx, "C", data.c.length - 1)} points={data.c} color={COLORS.C} lineWidth={3.4} />
      <Line ref={bindLine(ctx, "E", data.e.length - 1)} points={data.e} color={COLORS.E} lineWidth={3.4} />
      <Line ref={bindLine(ctx, "gap", data.gap.length / 2)} points={data.gap} segments color="#a0a8b8" lineWidth={0.9} />
      <Line ref={bindLine(ctx, "residual", data.residual.length / 2)} points={data.residual} segments color={COLORS.Y} lineWidth={1.1} />
      <Line ref={bindLine(ctx, "band", data.band.length / 2)} points={data.band} segments color={COLORS.band} lineWidth={5} />
      {data.candidatesC.map((pts, i) => (
        <Line key={`cc${i}`} ref={bindLine(ctx, `candC${i}`, pts.length - 1)} points={pts} color={COLORS.C} lineWidth={1.3} />
      ))}
      {data.candidatesE.map((pts, i) => (
        <Line key={`ce${i}`} ref={bindLine(ctx, `candE${i}`, pts.length - 1)} points={pts} color={COLORS.E} lineWidth={1} />
      ))}
      <Line ref={bindLine(ctx, "cCont", data.cContinue.length - 1)} points={data.cContinue} color={COLORS.C} lineWidth={2.4} {...dash} />
      <Line ref={bindLine(ctx, "cCess", data.cCessation.length - 1)} points={data.cCessation} color={COLORS.C} lineWidth={1.6} {...dash} dashSize={0.06} gapSize={0.1} />
      <Line ref={bindLine(ctx, "eCont", data.eContinue.length - 1)} points={data.eContinue} color={COLORS.E} lineWidth={2.4} {...dash} />

      <instancedMesh ref={bindSlot(ctx.yMesh)} args={[ctx.sphere, ctx.mats.y, data.y.length]} onPointerMove={hover} onPointerOut={unhover} />
      <instancedMesh ref={bindSlot(ctx.yfMesh)} args={[ctx.sphere, ctx.mats.yf, data.yFuture.length]} />
      <mesh ref={bindSlot(ctx.hover)} geometry={ctx.sphere} material={ctx.mats.hover} scale={1.9} visible={false} />

      <mesh ref={bindSlot(ctx.plane)} position={[data.boundaryX, 0, 1]} rotation={[0, Math.PI / 2, 0]} material={ctx.mats.plane}>
        <planeGeometry args={[4.4, 3.8]} />
      </mesh>
      <Line
        ref={bindLine(ctx, "boundaryLine", 4)}
        points={[
          [data.boundaryX, -1.9, -1.2],
          [data.boundaryX, -1.9, 3.2],
          [data.boundaryX, 1.9, 3.2],
          [data.boundaryX, 1.9, -1.2],
          [data.boundaryX, -1.9, -1.2],
        ]}
        color={COLORS.boundary}
        lineWidth={1.8}
      />
    </group>
  );
}

function ReadyProbe({ onReady }: { onReady?: (invalidate: () => void) => void }) {
  const { invalidate } = useThree();
  useEffect(() => {
    onReady?.(invalidate);
  }, [onReady, invalidate]);
  return null;
}

export default function StateSpaceScene(props: SceneProps) {
  return (
    <Canvas
      frameloop="demand"
      dpr={props.lowEnd ? [1, 1] : [1, 1.75]}
      camera={{ fov: 36, near: 0.1, far: 80, position: [0, 0.5, 12] }}
      gl={{ antialias: !props.lowEnd, alpha: true, powerPreference: props.lowEnd ? "low-power" : "default" }}
      aria-hidden="true"
      data-testid="scene-canvas"
      raycaster={{ params: { Mesh: {}, Line: { threshold: 0.1 }, LOD: {}, Points: { threshold: 0.1 }, Sprite: {} } }}
    >
      <ReadyProbe onReady={props.onReady} />
      <Rig position={props.position} userView={props.userView} lowEnd={props.lowEnd} reducedMotion={props.reducedMotion} />
      <Scene position={props.position} focus={props.focus} lowEnd={props.lowEnd} active={props.active} onHover={props.onHover} />
    </Canvas>
  );
}
