import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, Newsreader } from "next/font/google";
import type { ReactNode } from "react";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import shell from "@/components/shell.module.css";
import "./globals.css";

const description =
  "An interactive, evidence-bound observatory for Powerlifting State Research: latent capacity, expressed performance and noisy observation in synthetic dynamical systems, with source-hashed aggregate results and honest limits.";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "https://psr-observatory.vercel.app"),
  title: { default: "PSR Observatory", template: "%s | PSR Observatory" },
  description,
  applicationName: "PSR Observatory",
  authors: [{ name: "Powerlifting State Research contributors" }],
  keywords: ["synthetic dynamical systems", "probabilistic forecasting", "CRPS", "identifiability", "open science"],
  openGraph: {
    type: "website",
    siteName: "PSR Observatory",
    title: "PSR Observatory",
    description,
  },
  twitter: { card: "summary", title: "PSR Observatory", description },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f5f1" },
    { media: "(prefers-color-scheme: dark)", color: "#0c0e12" },
  ],
};

// Fonts are fetched at build time and self-hosted by Next.js (no runtime third-party request; no font files committed).
// The display serif is not preloaded and ships only the two static weights in use (no optical-size axis, no italic
// files): measured on mobile Lighthouse, the variable opsz + italic files (274 KB) delayed the first render.
const serif = Newsreader({ subsets: ["latin"], variable: "--font-newsreader", display: "swap", weight: ["400", "500"], style: ["normal"], preload: false });
const sans = IBM_Plex_Sans({ subsets: ["latin"], variable: "--font-plex-sans", display: "swap", weight: ["400", "500", "600"] });
const mono = IBM_Plex_Mono({ subsets: ["latin"], variable: "--font-plex-mono", display: "swap", weight: ["400", "500"], preload: false });

const themeScript = `try{var t=localStorage.getItem("psr-theme");if(t==="light"||t==="dark")document.documentElement.setAttribute("data-theme",t)}catch(e){}`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${serif.variable} ${sans.variable} ${mono.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <a className={shell.skip} href="#main">
          Skip to main content
        </a>
        <SiteHeader />
        <main id="main" tabIndex={-1}>
          {children}
        </main>
        <SiteFooter />
      </body>
    </html>
  );
}
