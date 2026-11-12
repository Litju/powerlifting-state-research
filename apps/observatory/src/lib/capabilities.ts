"use client";

import { useEffect, useState } from "react";

export function detectWebGL(): boolean {
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
    return Boolean(gl);
  } catch {
    return false;
  }
}

export function detectLowEnd(): boolean {
  const nav = navigator as Navigator & { deviceMemory?: number };
  const cores = nav.hardwareConcurrency ?? 8;
  const memory = nav.deviceMemory ?? 8;
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  const small = Math.min(window.screen.width, window.screen.height) < 500;
  return cores <= 4 || memory <= 4 || (coarse && small);
}

export type StageMode = "pending" | "scrub" | "static" | "diagram";

export interface Capabilities {
  mode: StageMode;
  lowEnd: boolean;
  reducedMotion: boolean;
  webgl: boolean;
}

/**
 * Resolves the presentation mode after hydration:
 * scrub = sticky WebGL stage driven by scroll; static = WebGL without scroll scrubbing (reduced motion);
 * diagram = semantic SVG diagram (no WebGL). `pending` is what the server renders (diagram + text).
 */
export function useCapabilities(): Capabilities {
  const [caps, setCaps] = useState<Capabilities>({ mode: "pending", lowEnd: false, reducedMotion: false, webgl: false });
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const forced = new URLSearchParams(window.location.search).get("scene");
    const compute = () => {
      // The WebGL probe itself is deferred to scene arming (creating a context is expensive on software renderers).
      const webgl = forced !== "off";
      const reducedMotion = mq.matches;
      const lowEnd = forced === "low" ? true : detectLowEnd();
      const mode: StageMode = !webgl ? "diagram" : reducedMotion ? "static" : "scrub";
      setCaps({ mode, lowEnd, reducedMotion, webgl });
    };
    compute();
    mq.addEventListener("change", compute);
    return () => mq.removeEventListener("change", compute);
  }, []);
  return caps;
}
