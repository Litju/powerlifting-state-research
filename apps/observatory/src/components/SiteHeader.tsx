"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import styles from "./shell.module.css";

const LINKS = [
  { href: "/", label: "Story" },
  { href: "/journey", label: "Research journey" },
  { href: "/forecast", label: "Forecasting lab" },
  { href: "/benchmarks", label: "Benchmarks" },
  { href: "/lab", label: "System lab" },
  { href: "/publication", label: "Publication" },
  { href: "/about", label: "About" },
];

type Theme = "light" | "dark";

function currentTheme(): Theme {
  const set = document.documentElement.getAttribute("data-theme");
  if (set === "light" || set === "dark") return set;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function SiteHeader() {
  const pathname = usePathname();
  const [theme, setTheme] = useState<Theme>("light");
  const [open, setOpen] = useState(false);
  const menuBtn = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reads the DOM-resolved theme once after hydration
    setTheme(currentTheme());
  }, []);
  // Close the compact menu on navigation and on Escape; return focus to its button.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- route change closes the disclosure
    setOpen(false);
  }, [pathname]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        menuBtn.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  function toggleTheme() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("psr-theme", next);
    } catch {
      /* storage may be unavailable; the choice then lasts for this page view */
    }
  }

  const story = pathname === "/";
  return (
    <header className={[styles.header, story ? `${styles.headerNight} night` : ""].join(" ")} data-zone="header">
      <div className={styles.headerInner}>
        <Link href="/" className={styles.brand} aria-label="PSR Observatory, home">
          <span className={styles.brandMark} aria-hidden="true" />
          PSR <span>Observatory</span>
        </Link>
        <nav aria-label="Primary" className={styles.primary}>
          <button
            ref={menuBtn}
            type="button"
            className={styles.menuBtn}
            aria-expanded={open}
            aria-controls="primary-links"
            onClick={() => setOpen((o) => !o)}
            data-testid="menu-button"
          >
            {open ? "Close" : "Menu"}
          </button>
          <ul id="primary-links" className={[styles.nav, open ? styles.navOpen : ""].join(" ")}>
            {LINKS.map((l) => (
              <li key={l.href}>
                <Link href={l.href} aria-current={pathname === l.href ? "page" : undefined} onClick={() => setOpen(false)}>
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        {story ? null : (
          <button type="button" className={styles.toggle} onClick={toggleTheme} aria-pressed={theme === "dark"} data-testid="theme-toggle">
            {theme === "dark" ? "Dark" : "Light"}
            <span className="sr-only"> theme</span>
          </button>
        )}
      </div>
    </header>
  );
}
