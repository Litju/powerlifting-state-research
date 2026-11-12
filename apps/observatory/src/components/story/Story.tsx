"use client";

import Link from "next/link";
import { motion, useScroll, useTransform, type MotionValue } from "motion/react";
import { Component, useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { detectWebGL, useCapabilities } from "@/lib/capabilities";
import { CHAPTERS, chapterCenter, type Chapter } from "@/lib/story";
import { Schematic } from "./Schematic";
import type { UserView } from "./StateSpaceScene";
import styles from "./story.module.css";

type SceneComponent = typeof import("./StateSpaceScene").default;

class SceneBoundary extends Component<{ onError: () => void; children: ReactNode }, { failed: boolean }> {
  override state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  override componentDidCatch() {
    this.props.onError();
  }
  override render() {
    return this.state.failed ? null : this.props.children;
  }
}

const INITIAL_VIEW: UserView = { dAz: 0, dEl: 0, zoom: 1 };

function ChapterCard({ chapter, index, progress, scrub }: { chapter: Chapter; index: number; progress: MotionValue<number>; scrub: boolean }) {
  const c = chapterCenter(index);
  const x = useTransform(progress, [c - 0.2, c, c + 0.2], [index % 2 === 0 ? -18 : 18, 0, index % 2 === 0 ? -18 : 18]);
  const Heading = index === 0 ? "h1" : "h2";
  return (
    <section
      id={chapter.id}
      data-chapter={index}
      aria-labelledby={`${chapter.id}-h`}
      tabIndex={-1}
      className={[styles.chapter, scrub ? "" : styles.chapterStatic, index === 0 ? styles.hero : ""].join(" ")}
    >
      <motion.div className={[styles.card, scrub ? "" : styles.cardStatic].join(" ")} style={scrub ? { x } : undefined}>
        <p className={styles.kicker}>{chapter.kicker}</p>
        <Heading id={`${chapter.id}-h`}>{chapter.title}</Heading>
        <p>{chapter.body}</p>
        {index === 0 ? (
          <>
            <p>
              <strong style={{ color: "var(--fg)" }}>Scroll to follow the story</strong>, or jump:
            </p>
            <ul className={styles.jump} aria-label="Jump to chapter">
              {CHAPTERS.slice(1).map((ch) => (
                <li key={ch.id}>
                  <a href={`#${ch.id}`}>{ch.kicker}</a>
                </li>
              ))}
            </ul>
          </>
        ) : null}
        {index === CHAPTERS.length - 1 ? (
          <p>
            <Link href="/forecast">Forecasting lab</Link> · <Link href="/journey">Research journey</Link> · <Link href="/lab">System lab</Link>
          </p>
        ) : null}
        {!scrub && index > 0 ? (
          <div style={{ marginTop: 16 }}>
            <Schematic focus={chapter.focus} id={`schem-${chapter.id}`} />
          </div>
        ) : null}
      </motion.div>
    </section>
  );
}

export function Story() {
  const caps = useCapabilities();
  const [sceneFailed, setSceneFailed] = useState(false);
  const mode = sceneFailed && caps.mode !== "pending" ? "diagram" : caps.mode;
  // `pending` (server render) uses the scrub layout so that hydration does not shift the page (CLS).
  const scrub = mode === "scrub";
  const scrubLayout = mode === "scrub" || mode === "pending";
  const [SceneImpl, setSceneImpl] = useState<SceneComponent | null>(null);
  // Defer loading the heavy WebGL chunk until the page is idle, so it never competes with first paint.
  useEffect(() => {
    if (mode !== "scrub" && mode !== "static") return;
    let cancelled = false;
    const arm = () => {
      if (!detectWebGL()) {
        setSceneFailed(true);
        return;
      }
      // Dynamic import on demand: the three.js chunk is not referenced by the initial HTML.
      import("./StateSpaceScene")
        .then((m) => {
          if (!cancelled) setSceneImpl(() => m.default);
        })
        .catch(() => setSceneFailed(true));
    };
    // Progressive enhancement: the semantic diagram is shown first; the heavy scene is armed by the first user
    // input, or after a short delay, whichever comes first.
    let armed = false;
    const once = () => {
      if (armed) return;
      armed = true;
      events.forEach((e) => window.removeEventListener(e, once));
      clearTimeout(timer);
      arm();
    };
    const events = ["pointerdown", "keydown", "wheel", "touchstart", "scroll"] as const;
    events.forEach((e) => window.addEventListener(e, once, { passive: true, once: false }));
    const timer = setTimeout(once, 4500);
    return () => {
      cancelled = true;
      armed = true;
      clearTimeout(timer);
      events.forEach((e) => window.removeEventListener(e, once));
    };
  }, [mode]);
  const showScene = (mode === "scrub" || mode === "static") && SceneImpl !== null;

  const storyRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: storyRef, offset: ["start start", "end end"] });
  const barScale = useTransform(scrollYProgress, [0, 1], [0, 1]);

  const [toggles, setToggles] = useState({ dynamics: true, noise: true, boundary: true });
  const [inView, setInView] = useState(true);
  const [activeIdx, setActiveIdx] = useState(0);
  const userView = useRef<UserView>({ ...INITIAL_VIEW });
  const invalidateRef = useRef<(() => void) | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number; id: number; touch: boolean } | null>(null);

  const publishView = useCallback(() => {
    const el = wrapRef.current;
    if (el) el.dataset.view = JSON.stringify({ dAz: +userView.current.dAz.toFixed(3), dEl: +userView.current.dEl.toFixed(3), zoom: +userView.current.zoom.toFixed(3) });
    invalidateRef.current?.();
  }, []);

  const nudge = useCallback(
    (patch: Partial<UserView> | ((v: UserView) => Partial<UserView>)) => {
      const next = typeof patch === "function" ? patch(userView.current) : patch;
      userView.current = { ...userView.current, ...next };
      userView.current.zoom = Math.min(1.7, Math.max(0.55, userView.current.zoom));
      publishView();
    },
    [publishView],
  );
  const reset = useCallback(() => {
    userView.current = { ...INITIAL_VIEW };
    publishView();
  }, [publishView]);

  useEffect(() => {
    publishView();
  }, [publishView, showScene]);

  // Visibility of the story drives rendering (no frames while off screen) and the chapter rail.
  useEffect(() => {
    const el = storyRef.current;
    if (!el) return;
    const io = new IntersectionObserver(([entry]) => setInView(Boolean(entry?.isIntersecting)), { threshold: 0 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  useEffect(() => {
    const nodes = document.querySelectorAll<HTMLElement>("[data-chapter]");
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) if (e.isIntersecting) setActiveIdx(Number((e.target as HTMLElement).dataset.chapter));
      },
      { rootMargin: "-45% 0px -45% 0px" },
    );
    nodes.forEach((n) => io.observe(n));
    return () => io.disconnect();
  }, []);

  const [docVisible, setDocVisible] = useState(true);
  useEffect(() => {
    const on = () => setDocVisible(!document.hidden);
    document.addEventListener("visibilitychange", on);
    return () => document.removeEventListener("visibilitychange", on);
  }, []);

  function onPointerDown(e: React.PointerEvent) {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    drag.current = { x: e.clientX, y: e.clientY, id: e.pointerId, touch: e.pointerType !== "mouse" };
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
  }
  function onPointerMove(e: React.PointerEvent) {
    const d = drag.current;
    if (!d || d.id !== e.pointerId) return;
    const dx = e.clientX - d.x;
    const dy = e.clientY - d.y;
    d.x = e.clientX;
    d.y = e.clientY;
    nudge((v) => ({ dAz: v.dAz - dx * 0.006, dEl: d.touch ? v.dEl : v.dEl + dy * 0.004 }));
  }
  function onPointerEnd(e: React.PointerEvent) {
    if (drag.current?.id === e.pointerId) drag.current = null;
  }
  function onKeyDown(e: React.KeyboardEvent) {
    const handled = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "+", "=", "-", "_", "0", "Escape"];
    if (!handled.includes(e.key)) return;
    e.preventDefault();
    if (e.key === "ArrowLeft") nudge((v) => ({ dAz: v.dAz - 0.12 }));
    else if (e.key === "ArrowRight") nudge((v) => ({ dAz: v.dAz + 0.12 }));
    else if (e.key === "ArrowUp") nudge((v) => ({ dEl: v.dEl + 0.08 }));
    else if (e.key === "ArrowDown") nudge((v) => ({ dEl: v.dEl - 0.08 }));
    else if (e.key === "+" || e.key === "=") nudge((v) => ({ zoom: v.zoom * 0.9 }));
    else if (e.key === "-" || e.key === "_") nudge((v) => ({ zoom: v.zoom / 0.9 }));
    else reset();
  }

  const toggle = (k: keyof typeof toggles) => setToggles((t) => ({ ...t, [k]: !t[k] }));
  const darkRail = true;

  return (
    <div ref={storyRef} className={styles.story} data-mode={mode} data-testid="story">
      {scrub ? <motion.div className={styles.progress} style={{ scaleX: barScale }} role="presentation" data-testid="progress-bar" /> : null}

      {scrub && inView ? (
        <nav className={[styles.rail, darkRail ? styles.railDark : ""].join(" ")} aria-label="Story chapters">
          <ol>
            {CHAPTERS.map((c, i) => (
              <li key={c.id}>
                <a href={`#${c.id}`} aria-current={activeIdx === i ? "step" : undefined} aria-label={`Chapter ${i + 1} of ${CHAPTERS.length}: ${c.kicker}`}>
                  <span className="label">{c.kicker}</span>
                  <span className={styles.pip} aria-hidden="true" />
                </a>
              </li>
            ))}
          </ol>
        </nav>
      ) : null}

      <div className={[styles.stage, scrubLayout ? styles.stageSticky : ""].join(" ")} data-testid="stage">
        {showScene ? (
          <div
            ref={wrapRef}
            className={styles.canvasWrap}
            role="group"
            tabIndex={0}
            aria-label="Interactive 3D state-space illustration. Drag horizontally or use the arrow keys to rotate, plus and minus to zoom, zero to reset the view."
            aria-describedby="scene-desc"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerEnd}
            onPointerCancel={onPointerEnd}
            onKeyDown={onKeyDown}
            data-testid="scene-wrap"
          >
            <SceneBoundary onError={() => setSceneFailed(true)}>
              {SceneImpl ? <SceneImpl
                progress={scrub ? scrollYProgress : null}
                userView={userView}
                toggles={toggles}
                lowEnd={caps.lowEnd}
                reducedMotion={caps.reducedMotion}
                active={inView && docVisible}
                fixedProgress={0}
                onReady={(inv) => {
                  invalidateRef.current = inv;
                }}
              /> : null}
            </SceneBoundary>
          </div>
        ) : (
          <div className={styles.diagramWrap}>
            <Schematic focus={["C", "E", "Y", "boundary", "future", "gap"]} id="schem-hero" />
          </div>
        )}

        <p id="scene-desc" className="sr-only">
          {showScene
            ? "Conceptual three-dimensional illustration, not measured data. Time runs along the horizontal axis and performance along the vertical axis. The depth axis is the suppression state. Latent capacity C is a smooth teal curve in the base plane. Expressed performance E is an amber curve pulled out of that plane and below C. Observed noisy assessments Y are violet points scattered around E. A translucent red plane marks the information boundary at day 223, with the forecast origin at day 224; dashed branches to its right are conceptual plan-dependent futures."
            : "Conceptual diagram, not measured data, showing latent capacity C, expressed performance E, noisy observations Y and the information boundary at day 223."}
        </p>

        <div className={styles.legend}>
          <span className={styles.caption} data-testid="scene-caption">
            Conceptual illustration - not measured data
          </span>
          <ul aria-label="Legend">
            <li>
              <span className={styles.dot} style={{ background: "var(--c-latent)" }} aria-hidden="true" /> C latent capacity
            </li>
            <li>
              <span className={styles.dot} style={{ background: "var(--c-expressed)" }} aria-hidden="true" /> E expressed performance
            </li>
            <li>
              <span className={styles.dot} style={{ background: "var(--c-observed)" }} aria-hidden="true" /> Y observed, noisy
            </li>
            <li>
              <span className={styles.dot} style={{ background: "var(--c-boundary)" }} aria-hidden="true" /> information boundary
            </li>
          </ul>
        </div>

        {showScene ? (
          <div className={styles.controls} role="toolbar" aria-label="Scene controls" data-testid="scene-controls">
            <button type="button" className={styles.ctl} aria-pressed={toggles.dynamics} onClick={() => toggle("dynamics")}>
              Dynamics
            </button>
            <button type="button" className={styles.ctl} aria-pressed={toggles.noise} onClick={() => toggle("noise")}>
              Observation noise
            </button>
            <button type="button" className={styles.ctl} aria-pressed={toggles.boundary} onClick={() => toggle("boundary")}>
              Information boundary
            </button>
            <button type="button" className={styles.ctl} onClick={() => nudge((v) => ({ zoom: v.zoom * 0.88 }))} aria-label="Zoom in">
              +
            </button>
            <button type="button" className={styles.ctl} onClick={() => nudge((v) => ({ zoom: v.zoom / 0.88 }))} aria-label="Zoom out">
              −
            </button>
            <button type="button" className={styles.ctl} onClick={reset} data-testid="scene-reset">
              Reset view
            </button>
          </div>
        ) : null}
      </div>

      <div className={[styles.chapters, scrubLayout ? styles.chaptersOverlay : ""].join(" ")}>
        {CHAPTERS.map((c, i) => (
          <ChapterCard key={c.id} chapter={c} index={i} progress={scrollYProgress} scrub={scrubLayout} />
        ))}
      </div>
    </div>
  );
}
