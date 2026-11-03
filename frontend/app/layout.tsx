import type { Metadata, Viewport } from "next";
import type * as React from "react";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";

import { SiteHeader } from "@/components/landing/SiteHeader";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { Toaster } from "@/components/ui/sonner";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "AI Governance Intake",
    template: "%s · AI Governance Intake",
  },
  description:
    "Bring a project into AI governance: describe it or point at the repository, confirm what we infer, and get an EU AI Act classification.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f7f7" },
    { media: "(prefers-color-scheme: dark)", color: "#0f1417" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${GeistSans.variable} ${GeistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        <ThemeProvider>
          <a href="#content" className="skip-link">
            Skip to content
          </a>
          <SiteHeader />
          <main id="content" tabIndex={-1} className="flex flex-1 flex-col outline-none">
            {children}
          </main>
          <Toaster richColors position="bottom-right" />
        </ThemeProvider>
      </body>
    </html>
  );
}
