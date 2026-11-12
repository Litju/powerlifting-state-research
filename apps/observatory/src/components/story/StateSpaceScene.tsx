"use client";

import { Line } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import type { MotionValue } from "motion/react";
import * as THREE from "three";
import { buildSceneData, type V3 } from "@/lib/scene-data";
import { cameraPose, layerWeights, type Layer } from "@/lib/story";

export interface UserView {
  dAz: number;
  dEl: number;
  zoom: number;
}

export interface SceneProps {
  progress: MotionValue<number> | null;
  userView: React.RefObject<UserView>;
  toggles: { dynamics: boolean; noise: boolean; boundary: boolean };
  lowEnd: boolean;
  reducedMotion: boolean;
  active: boolean;
  /** Static focus used when the camera does not follow scroll. */
  fixedProgress: number;
  onReady?: (invalidate: () => void) => void;
}

const COLORS = {
  C: "#5ed3d9",
  E: "#f2a65a",
  Y: "#bba8ff",
  boundary: "#ff8d84",
  grid: "#3a4252",
};

type Opacity = { material: { opacity: number } };

function setOpacity(ref: { node: unknown }, value: number) {
  const target = ref.node as Opacity | null;
  if (target?.material) target.material.opacity = value;
}

function Rig({ progress, userView, fixedProgress, lowEnd }: Pick<SceneProps, "progress" | "userView" | "fixedProgress" | "lowEnd">) {
  const { camera, invalidate, size } = useThree();
  const cur = useRef({ az: 0, el: 0, r: 0, tx: 0, ty: 0, tz: 0, init: false });
  const look = useMemo(() => new THREE.Vector3(), []);
  useEffect(() => {
    if (!progress) return;
    return progress.on("change", () => invalidate());
  }, [progress, invalidate]);
  // On wide screens the text card sits on the left, so shift the optical centre of the scene to the right.
  useEffect(() => {
    const cam = camera as THREE.PerspectiveCamera;
    if (size.width / size.height > 1.15) cam.setViewOffset(size.width, size.height, -size.width * 0.14, 0, size.width, size.height);
    else cam.clearViewOffset();
    invalidate();
    return () => cam.clearViewOffset();
  }, [camera, size, invalidate]);
  useFrame((_, delta) => {
    const p = progress ? progress.get() : fixedProgress;
    const pose = cameraPose(p);
    const u = userView.current;
    const target = { az: pose.az + u.dAz, el: Math.min(1.35, Math.max(-0.2, pose.el + u.dEl)), r: pose.r * u.zoom, tx: pose.tx, ty: pose.ty, tz: pose.tz };
    const c = cur.current;
    if (!c.init) {
      Object.assign(c, target, { init: true });
    }
    const k = 1 - Math.exp(-delta * (lowEnd ? 12 : 9));
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

type Slot<T = unknown> = { node: T | null };
const slot = <T,>(): Slot<T> => ({ node: null });
const bind = <T,>(s: Slot<T>) => (n: T | null) => {
  s.node = n;
};

function makeContext(lowEnd: boolean) {
  return {
    C: slot(),
    E: slot(),
    gap: slot(),
    boundaryLine: slot(),
    cCont: slot(),
    cCess: slot(),
    eCont: slot(),
    residual: slot(),
    plane: slot<THREE.Mesh>(),
    pulseC: slot<THREE.Mesh>(),
    pulseE: slot<THREE.Mesh>(),
    sphere: new THREE.SphereGeometry(0.075, lowEnd ? 6 : 12, lowEnd ? 6 : 12),
    pulseGeo: new THREE.SphereGeometry(0.08, 10, 10),
    yMat: new THREE.MeshBasicMaterial({ color: COLORS.Y, transparent: true }),
    yFutMat: new THREE.MeshBasicMaterial({ color: COLORS.Y, transparent: true, wireframe: true }),
    planeMat: new THREE.MeshBasicMaterial({ color: COLORS.boundary, transparent: true, side: THREE.DoubleSide, depthWrite: false }),
    pulseMat: new THREE.MeshBasicMaterial({ color: "#ffffff" }),
    clock: { t: 0 },
    perf: { slow: 0, frames: 0, throttled: false },
  };
}
type Ctx = ReturnType<typeof makeContext>;

function updateLayers(ctx: Ctx, data: ReturnType<typeof buildSceneData>, p: number, toggles: SceneProps["toggles"], delta: number, animate: boolean): boolean {
  const perf = ctx.perf;
  perf.frames += 1;
  if (delta > 0.05) perf.slow += 1;
  if (perf.frames >= 12 && perf.slow / perf.frames > 0.5) perf.throttled = true;
  const run = animate && !perf.throttled;
  const w = layerWeights(p);
  const val = (layer: Layer, on = true) => (on ? w[layer] : 0);
  setOpacity(ctx.C, val("C"));
  setOpacity(ctx.E, val("E"));
  setOpacity(ctx.gap, val("gap") * 0.9);
  setOpacity(ctx.residual, val("Y", toggles.noise) * 0.8);
  setOpacity(ctx.boundaryLine, val("boundary", toggles.boundary));
  setOpacity(ctx.cCont, val("future", toggles.boundary) * 0.9);
  setOpacity(ctx.cCess, val("future", toggles.boundary) * 0.9);
  setOpacity(ctx.eCont, val("future", toggles.boundary) * 0.9);
  ctx.yMat.opacity = val("Y", toggles.noise);
  ctx.yFutMat.opacity = val("future", toggles.boundary && toggles.noise);
  ctx.planeMat.opacity = 0.16 * val("boundary", toggles.boundary);
  if (ctx.plane.node) ctx.plane.node.visible = toggles.boundary;

  // Dynamics: a pulse travels along C and E, illustrating accumulation and suppression.
  const pc = ctx.pulseC.node;
  const pe = ctx.pulseE.node;
  if (pc && pe) {
    pc.visible = pe.visible = toggles.dynamics;
    if (run) ctx.clock.t = (ctx.clock.t + delta * 0.12) % 1;
    const f = ctx.clock.t * (data.c.length - 1);
    const i = Math.floor(f);
    const t = f - i;
    const a = data.c[i]!;
    const b = data.c[Math.min(i + 1, data.c.length - 1)]!;
    const ea = data.e[i]!;
    const eb = data.e[Math.min(i + 1, data.e.length - 1)]!;
    pc.position.set(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t);
    pe.position.set(ea[0] + (eb[0] - ea[0]) * t, ea[1] + (eb[1] - ea[1]) * t, ea[2] + (eb[2] - ea[2]) * t);
  }
  return run;
}

function Layers({ progress, toggles, fixedProgress, reducedMotion, active, lowEnd }: Pick<SceneProps, "progress" | "toggles" | "fixedProgress" | "reducedMotion" | "active" | "lowEnd">) {
  const { invalidate } = useThree();
  const data = useMemo(() => buildSceneData(lowEnd ? 4 : 2), [lowEnd]);
  const ctx = useMemo(() => makeContext(lowEnd), [lowEnd]);
  const animate = toggles.dynamics && !reducedMotion && active;

  useEffect(() => {
    invalidate();
  }, [toggles, invalidate, active]);

  useFrame((_, delta) => {
    // Adaptive guard: if frames are consistently slow (software rendering, weak GPU), stop the continuous
    // pulse animation. Scroll and drag still render on demand.
    const run = updateLayers(ctx, data, progress ? progress.get() : fixedProgress, toggles, delta, animate);
    if (run) invalidate();
  });

  const dash = { dashed: true, dashSize: 0.18, gapSize: 0.12 } as const;
  return (
    <group>
      {/* floor grid and axes */}
      <Line points={data.grid} segments color={COLORS.grid} lineWidth={0.6} transparent opacity={0.55} />
      <Line points={data.axes.x} color="#8d96a8" lineWidth={1.2} />
      <Line points={data.axes.y} color="#8d96a8" lineWidth={1.2} />
      <Line points={data.axes.z} color="#8d96a8" lineWidth={1.2} />

      <Line ref={bind(ctx.C) as never} points={data.c} color={COLORS.C} lineWidth={3.2} transparent />
      <Line ref={bind(ctx.E) as never} points={data.e} color={COLORS.E} lineWidth={3.2} transparent />
      <Line ref={bind(ctx.gap) as never} points={data.gap} segments color="#9aa3b5" lineWidth={0.9} transparent />
      <Line ref={bind(ctx.residual) as never} points={data.residual} segments color={COLORS.Y} lineWidth={0.9} transparent />

      <Line ref={bind(ctx.cCont) as never} points={data.cContinue} color={COLORS.C} lineWidth={2.4} transparent {...dash} />
      <Line ref={bind(ctx.cCess) as never} points={data.cCessation} color={COLORS.C} lineWidth={1.6} transparent {...dash} dashSize={0.06} gapSize={0.1} />
      <Line ref={bind(ctx.eCont) as never} points={data.eContinue} color={COLORS.E} lineWidth={2.4} transparent {...dash} />

      {data.y.map((p, i) => (
        <mesh key={`y${i}`} position={p as V3} geometry={ctx.sphere} material={ctx.yMat} />
      ))}
      {data.yFuture.map((p, i) => (
        <mesh key={`f${i}`} position={p as V3} geometry={ctx.sphere} material={ctx.yFutMat} scale={1.5} />
      ))}

      <mesh ref={bind(ctx.plane) as never} position={[data.boundaryX, 0, 1]} rotation={[0, Math.PI / 2, 0]} material={ctx.planeMat}>
        <planeGeometry args={[4.4, 3.8]} />
      </mesh>
      <Line
        ref={bind(ctx.boundaryLine) as never}
        points={[
          [data.boundaryX, -1.9, -1.2],
          [data.boundaryX, -1.9, 3.2],
          [data.boundaryX, 1.9, 3.2],
          [data.boundaryX, 1.9, -1.2],
          [data.boundaryX, -1.9, -1.2],
        ]}
        color={COLORS.boundary}
        lineWidth={1.8}
        transparent
      />
      <mesh ref={bind(ctx.pulseC) as never} geometry={ctx.pulseGeo} material={ctx.pulseMat} />
      <mesh ref={bind(ctx.pulseE) as never} geometry={ctx.pulseGeo} material={ctx.pulseMat} />
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
      camera={{ fov: 38, near: 0.1, far: 80, position: [8, 4, 10] }}
      gl={{ antialias: !props.lowEnd, alpha: true, powerPreference: props.lowEnd ? "low-power" : "default" }}
      style={{ touchAction: "pan-y" }}
      aria-hidden="true"
      data-testid="scene-canvas"
    >
      <ReadyProbe onReady={props.onReady} />
      <Rig progress={props.progress} userView={props.userView} fixedProgress={props.fixedProgress} lowEnd={props.lowEnd} />
      <Layers
        progress={props.progress}
        toggles={props.toggles}
        fixedProgress={props.fixedProgress}
        reducedMotion={props.reducedMotion}
        active={props.active}
        lowEnd={props.lowEnd}
      />
    </Canvas>
  );
}
