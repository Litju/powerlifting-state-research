"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import styles from "./shell.module.css";

const LINKS = [
  { href: "/", label: "Observatory" },
  { href: "/lab", label: "System lab" },
  { href: "/journey", label: "Research journey" },
  { href: "/benchmarks", label: "Benchmarks" },
  { href: "/forecast", label: "Forecasting lab" },
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
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reads the DOM-resolved theme once after hydration
    setTheme(currentTheme());
  }, []);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("psr-theme", next);
    } catch {
      /* storage may be unavailable; the choice then lasts for this page view */
    }
  }

  return (
    <header className={styles.header}>
      <div className={styles.headerInner}>
        <Link href="/" className={styles.brand}>
          PSR <span>Observatory</span>
        </Link>
        <nav aria-label="Primary">
          <ul className={styles.nav}>
            {LINKS.map((l) => (
              <li key={l.href}>
                <Link href={l.href} aria-current={pathname === l.href ? "page" : undefined}>
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <button type="button" className={styles.toggle} onClick={toggle} aria-pressed={theme === "dark"} data-testid="theme-toggle">
          {theme === "dark" ? "Dark theme" : "Light theme"}
        </button>
      </div>
    </header>
  );
}
