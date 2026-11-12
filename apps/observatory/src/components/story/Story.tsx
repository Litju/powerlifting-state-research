"use client";

import { motionValue, useMotionValueEvent } from "motion/react";
import { Component, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { detectLowEnd, detectWebGL } from "@/lib/capabilities";
import { ACTS, BEATS, BEAT_ACT, positionFromRects, sceneState, type PanelId } from "@/lib/story";
import type { StoryEvidence } from "@/lib/story-evidence";
import type { Assessment } from "@/lib/scene-data";
import { BeatContent } from "./content";
import { G2Panel, RidgePanel, UncertaintyPanel } from "./EvidencePanels";
import type { FocusLayer, UserView } from "./StateSpaceScene";
import { StoryFigure } from "./StoryFigure";
import styles from "./story.module.css";

type SceneComponent = typeof import("./StateSpaceScene").default;

/**
 * Layout contract. The sticky split stage is used only when there is room for a reading column beside a visual
 * field and the reader has not asked for reduced motion; otherwise every beat carries its own inline figure.
 * The same query is mirrored in story.module.css so that server-rendered HTML already has the right layout.
 */
export const STAGE_QUERY = "(min-width: 960px) and (min-height: 600px) and (prefers-reduced-motion: no-preference)";

type Mode = "pending" | "inline" | "stage-figure" | "stage-webgl";

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
const FOCUS_ITEMS: { id: Exclude<FocusLayer, null>; label: string; swatch: string }[] = [
  { id: "C", label: "C capacity", swatch: "var(--c-latent)" },
  { id: "E", label: "E expressed", swatch: "var(--c-expressed)" },
  { id: "Y", label: "Y observed", swatch: "var(--c-observed)" },
  { id: "boundary", label: "Boundary", swatch: "var(--c-boundary)" },
];

function Panel({ id, evidence, step, slot }: { id: PanelId; evidence: StoryEvidence; step: number; slot: "stage" | "inline" }) {
  if (id === "g2") return <G2Panel evidence={evidence} slot={slot} />;
  if (id === "ridge") return <RidgePanel evidence={evidence} slot={slot} />;
  return <UncertaintyPanel evidence={evidence} step={step} slot={slot} />;
}

/** The nearest conceptual (non-panel) beat at or before index i: the figure shown behind an evidence panel. */
function conceptualBeat(i: number): string {
  for (let k = i; k >= 0; k -= 1) if (!BEATS[k]!.panel) return BEATS[k]!.id;
  return BEATS[0]!.id;
}

export function Story({ evidence }: { evidence: StoryEvidence }) {
  const [mode, setMode] = useState<Mode>("pending");
  const [lowEnd, setLowEnd] = useState(false);
  const [SceneImpl, setSceneImpl] = useState<SceneComponent | null>(null);
  const position = useMemo(() => motionValue(0), []);
  const [beat, setBeat] = useState(0);
  const [focus, setFocus] = useState<FocusLayer>(null);
  const [hovered, setHovered] = useState<Assessment | null>(null);
  const [visible, setVisible] = useState(true);
  const beatEls = useRef<(HTMLElement | null)[]>([]);
  const rootRef = useRef<HTMLDivElement>(null);
  const sceneLayer = useRef<HTMLDivElement>(null);
  const panelEls = useRef<Partial<Record<PanelId, HTMLDivElement | null>>>({});
  const progressEl = useRef<HTMLSpanElement>(null);
  const userView = useRef<UserView>({ ...INITIAL_VIEW });
  const invalidateRef = useRef<(() => void) | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number; id: number; touch: boolean } | null>(null);

  // Resolve the layout mode after hydration, and follow viewport / preference changes.
  useEffect(() => {
    const mq = window.matchMedia(STAGE_QUERY);
    const forced = new URLSearchParams(window.location.search).get("scene");
    const compute = () => {
      if (!mq.matches) return setMode("inline");
      setMode(forced === "off" || !detectWebGL() ? "stage-figure" : "stage-webgl");
    };
    // eslint-disable-next-line react-hooks/set-state-in-effect -- device capability is only known after hydration
    setLowEnd(forced === "low" || detectLowEnd());
    compute();
    mq.addEventListener("change", compute);
    return () => mq.removeEventListener("change", compute);
  }, []);

  // Lazy WebGL: the three.js chunk is requested only in stage mode, after first input or when the page is idle.
  useEffect(() => {
    if (mode !== "stage-webgl" || SceneImpl) return;
    let done = false;
    const arm = () => {
      if (done) return;
      done = true;
      cleanup();
      import("./StateSpaceScene")
        .then((m) => setSceneImpl(() => m.default))
        .catch(() => setMode("stage-figure"));
    };
    const events = ["pointerdown", "keydown", "wheel", "touchstart", "scroll"] as const;
    events.forEach((e) => window.addEventListener(e, arm, { passive: true }));
    const idle = (window as Window & { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number }).requestIdleCallback;
    const timer = idle ? idle(arm, { timeout: 2500 }) : window.setTimeout(arm, 1500);
    function cleanup() {
      events.forEach((e) => window.removeEventListener(e, arm));
      if (!idle) window.clearTimeout(timer);
    }
    return () => {
      done = true;
      cleanup();
    };
  }, [mode, SceneImpl]);

  const stage = mode === "stage-figure" || mode === "stage-webgl";

  // Story position from native scroll: the reading line is the centre of the area below the header.
  useEffect(() => {
    if (!stage) return;
    let raf = 0;
    const update = () => {
      raf = 0;
      const header = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--header-h")) || 56;
      const line = header + (window.innerHeight - header) * 0.5;
      const rects = beatEls.current.map((el) => {
        const r = el?.getBoundingClientRect();
        return { top: r?.top ?? 0, height: r?.height ?? 1 };
      });
      const p = positionFromRects(rects, line);
      position.set(p);
      const b = Math.floor(p);
      setBeat((prev) => (prev === b ? prev : b));
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [stage, position]);

  // Panels and the scene layer cross-fade from the same pure state the camera uses (no React render per frame).
  const applyStage = useCallback(
    (p: number) => {
      const st = sceneState(p);
      const maxPanel = Math.max(st.panels.g2, st.panels.ridge, st.panels.uncertainty);
      if (sceneLayer.current) sceneLayer.current.style.opacity = String(1 - 0.88 * maxPanel);
      (Object.keys(st.panels) as PanelId[]).forEach((id) => {
        const el = panelEls.current[id];
        if (!el) return;
        const o = st.panels[id];
        el.style.opacity = String(o);
        el.style.visibility = o > 0.02 ? "visible" : "hidden";
        el.style.transform = `translateY(${(1 - o) * 12}px)`;
        el.toggleAttribute("inert", o < 0.5);
      });
      if (progressEl.current) progressEl.current.style.transform = `scaleX(${Math.min(1, (p + 0.5) / BEATS.length)})`;
    },
    [],
  );
  useMotionValueEvent(position, "change", applyStage);
  useEffect(() => {
    if (stage) applyStage(position.get());
  }, [stage, applyStage, position, beat]);

  // Rendering only while the story is on screen and the document is visible.
  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setVisible(Boolean(e?.isIntersecting)), { threshold: 0 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  // One-shot drawing of inline figures as each beat first enters the viewport.
  useEffect(() => {
    if (mode !== "inline") return;
    const els = beatEls.current.filter(Boolean) as HTMLElement[];
    els.forEach((el) => {
      if (!el.dataset.inview) el.dataset.inview = "false";
    });
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries)
          if (e.isIntersecting) {
            (e.target as HTMLElement).dataset.inview = "true";
            io.unobserve(e.target);
          }
      },
      { rootMargin: "0px 0px -20% 0px" },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [mode]);

  const publishView = useCallback(() => {
    const el = wrapRef.current;
    if (el) el.dataset.view = JSON.stringify({ dAz: +userView.current.dAz.toFixed(3), dEl: +userView.current.dEl.toFixed(3), zoom: +userView.current.zoom.toFixed(3) });
    invalidateRef.current?.();
  }, []);
  const nudge = useCallback(
    (patch: (v: UserView) => Partial<UserView>) => {
      userView.current = { ...userView.current, ...patch(userView.current) };
      userView.current.zoom = Math.min(1.7, Math.max(0.55, userView.current.zoom));
      userView.current.dEl = Math.min(0.9, Math.max(-0.5, userView.current.dEl));
      publishView();
    },
    [publishView],
  );
  const reset = useCallback(() => {
    userView.current = { ...INITIAL_VIEW };
    setFocus(null);
    publishView();
  }, [publishView]);
  useEffect(() => {
    publishView();
  }, [publishView, SceneImpl]);

  function onPointerDown(e: React.PointerEvent) {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    drag.current = { x: e.clientX, y: e.clientY, id: e.pointerId, touch: e.pointerType !== "mouse" };
    if (e.pointerType === "mouse") (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
  }
  function onPointerMove(e: React.PointerEvent) {
    const d = drag.current;
    if (!d || d.id !== e.pointerId) return;
    const dx = e.clientX - d.x;
    const dy = e.clientY - d.y;
    d.x = e.clientX;
    d.y = e.clientY;
    // Touch only orbits horizontally; vertical touch movement stays native scrolling (touch-action: pan-y).
    nudge((v) => ({ dAz: v.dAz - dx * 0.006, dEl: d.touch ? v.dEl : v.dEl + dy * 0.004 }));
  }
  function onPointerEnd(e: React.PointerEvent) {
    if (drag.current?.id === e.pointerId) drag.current = null;
  }
  function onKeyDown(e: React.KeyboardEvent) {
    const keys = ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "+", "=", "-", "_", "0"];
    if (!keys.includes(e.key)) return;
    e.preventDefault();
    if (e.key === "ArrowLeft") nudge((v) => ({ dAz: v.dAz - 0.12 }));
    else if (e.key === "ArrowRight") nudge((v) => ({ dAz: v.dAz + 0.12 }));
    else if (e.key === "ArrowUp") nudge((v) => ({ dEl: v.dEl + 0.08 }));
    else if (e.key === "ArrowDown") nudge((v) => ({ dEl: v.dEl - 0.08 }));
    else if (e.key === "+" || e.key === "=") nudge((v) => ({ zoom: v.zoom * 0.9 }));
    else if (e.key === "-" || e.key === "_") nudge((v) => ({ zoom: v.zoom / 0.9 }));
    else reset();
  }
  useEffect(() => {
    invalidateRef.current?.();
  }, [focus]);

  const current = BEATS[Math.min(beat, BEATS.length - 1)]!;
  const act = BEAT_ACT[Math.min(beat, BEATS.length - 1)]!;
  const panelBeat = Boolean(current.panel);
  const showScene = mode === "stage-webgl" && SceneImpl !== null;
  const stepFor = (id: PanelId) => (id === "uncertainty" ? sceneState(position.get()).panelStep : 0);

  return (
    <div ref={rootRef} className={`night ${styles.root}`} data-testid="story" data-mode={mode}>
      <div className={styles.story}>
        <div className={styles.narrative}>
          {ACTS.map((a, ai) => (
            <section
              key={a.id}
              id={a.id}
              className={styles.act}
              aria-labelledby={ai === 0 ? undefined : `${a.id}-h`}
              aria-label={ai === 0 ? `Act ${a.numeral}, ${a.kicker}` : undefined}
              data-act={ai}
              tabIndex={-1}
            >
              {a.beats.map((b, bi) => {
                const index = BEATS.indexOf(b);
                return (
                  <div
                    key={b.id}
                    ref={(n) => {
                      beatEls.current[index] = n;
                    }}
                    className={[styles.beat, ai === 0 && bi === 0 ? styles.hero : ""].join(" ")}
                    data-beat={b.id}
                    data-active={stage ? index === beat : undefined}
                  >
                    <div className={styles.text} data-zone="text">
                      {ai > 0 && bi === 0 ? (
                        <header className={styles.actHead}>
                          <p className={styles.kicker}>
                            <span className={styles.numeral}>Act {a.numeral}</span> {a.kicker}
                          </p>
                          <h2 id={`${a.id}-h`}>{a.title}</h2>
                        </header>
                      ) : null}
                      <BeatContent beatId={b.id} evidence={evidence} />
                    </div>
                    <div className={styles.inlineVisual} data-zone="inline-visual">
                      {b.panel ? <Panel id={b.panel} evidence={evidence} step={9} slot="inline" /> : <StoryFigure beatId={b.id} id={`fig-${b.id}`} height={250} />}
                    </div>
                  </div>
                );
              })}
            </section>
          ))}
        </div>

        <aside className={styles.stage} aria-label="Story visual" data-testid="stage">
          {stage ? (
            <>
              <div className={styles.stageBar} data-zone="stage-bar">
                <nav aria-label="Story acts" className={styles.acts}>
                  <ol>
                    {ACTS.map((a, i) => (
                      <li key={a.id}>
                        <a href={`#${a.id}`} aria-current={act === i ? "step" : undefined}>
                          <span className={styles.actNum}>{a.numeral}</span>
                          <span className={styles.actLabel}>{a.short}</span>
                        </a>
                      </li>
                    ))}
                  </ol>
                  <span className={styles.track} aria-hidden="true">
                    <span ref={progressEl} className={styles.trackFill} data-testid="progress-bar" />
                  </span>
                </nav>
                <p className={[styles.badge, panelBeat ? styles.badgeEvidence : ""].join(" ")} data-testid="scene-caption">
                  {panelBeat ? "Evidence · aggregate study results" : "Illustrative simulation · not measured data"}
                </p>
              </div>

              <div className={styles.stageField} data-zone="stage-field">
                <div ref={sceneLayer} className={styles.sceneLayer}>
                  {showScene ? (
                    <div
                      ref={wrapRef}
                      className={styles.canvasWrap}
                      role="group"
                      tabIndex={0}
                      aria-label="Interactive 3D illustration. Drag or use the arrow keys to rotate, plus and minus to zoom, zero to reset. Hover a point to read its values."
                      aria-describedby="scene-desc"
                      onPointerDown={onPointerDown}
                      onPointerMove={onPointerMove}
                      onPointerUp={onPointerEnd}
                      onPointerCancel={onPointerEnd}
                      onKeyDown={onKeyDown}
                      data-testid="scene-wrap"
                    >
                      <SceneBoundary onError={() => setMode("stage-figure")}>
                        <SceneImpl
                          position={position}
                          userView={userView}
                          focus={focus}
                          lowEnd={lowEnd}
                          reducedMotion={false}
                          active={visible}
                          onHover={setHovered}
                          onReady={(inv) => {
                            invalidateRef.current = inv;
                          }}
                        />
                      </SceneBoundary>
                    </div>
                  ) : (
                    <div className={styles.figureFallback}>
                      <StoryFigure key={conceptualBeat(beat)} beatId={conceptualBeat(beat)} id="fig-stage" />
                    </div>
                  )}
                </div>
                {(["g2", "ridge", "uncertainty"] as PanelId[]).map((id) => (
                  <div
                    key={id}
                    ref={(n) => {
                      panelEls.current[id] = n;
                    }}
                    className={styles.panelLayer}
                    style={{ opacity: 0, visibility: "hidden" }}
                    data-testid={`panel-${id}`}
                  >
                    <div className={styles.panelCard}>
                      <Panel id={id} evidence={evidence} step={stepFor(id)} slot="stage" />
                    </div>
                  </div>
                ))}
                <p id="scene-desc" className="sr-only">
                  Conceptual three-dimensional illustration from the public simulator, not measured data. Time runs left to right, kilograms upwards, and suppression S into depth. Latent capacity C is a teal
                  curve in the back plane; expressed performance E is an amber curve pulled forward by suppression; observed assessments Y are violet points. A red plane marks the end of history at day
                  223.
                </p>
              </div>

              <div className={styles.stageFoot} data-zone="stage-controls">
                {panelBeat ? (
                  <p className={styles.footNote}>Use the switches, and hover or focus a mark for exact values. Open “Method, source and data” for the interval scope, the hashed source and a data table.</p>
                ) : showScene ? (
                  <>
                    <div className={styles.legend} role="group" aria-label="Focus a layer">
                      {FOCUS_ITEMS.map((f) => (
                        <button key={f.id} type="button" aria-pressed={focus === f.id} onClick={() => setFocus((x) => (x === f.id ? null : f.id))} className={styles.legendBtn}>
                          <span className={styles.swatch} style={{ background: f.swatch }} aria-hidden="true" />
                          {f.label}
                        </button>
                      ))}
                    </div>
                    <div className={styles.view} role="toolbar" aria-label="Scene view" data-testid="scene-controls">
                      <button type="button" onClick={() => nudge((v) => ({ zoom: v.zoom * 0.88 }))} aria-label="Zoom in">
                        +
                      </button>
                      <button type="button" onClick={() => nudge((v) => ({ zoom: v.zoom / 0.88 }))} aria-label="Zoom out">
                        −
                      </button>
                      <button type="button" onClick={reset} data-testid="scene-reset">
                        Reset
                      </button>
                    </div>
                    <p className={styles.readout} aria-live="polite" data-testid="scene-readout">
                      {hovered
                        ? `Day ${hovered.day} · Y ${hovered.y.toFixed(1)} kg${sceneState(position.get()).layers.C > 0.4 ? ` · hidden: E ${hovered.E.toFixed(1)}, C ${hovered.C.toFixed(1)} kg` : ""} (illustrative)`
                        : "Hover a point to read it. Drag to rotate."}
                    </p>
                  </>
                ) : (
                  <ul className={styles.legend} aria-label="Legend">
                    {FOCUS_ITEMS.map((f) => (
                      <li key={f.id} className={styles.legendItem}>
                        <span className={styles.swatch} style={{ background: f.swatch }} aria-hidden="true" />
                        {f.label}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
