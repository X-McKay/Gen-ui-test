"use client";

import * as React from "react";
import { MoonStar, SunMedium } from "lucide-react";
import { useTheme } from "next-themes";

import { Button } from "@/components/ui/button";

const subscribeNoop = () => () => {};

/**
 * Switches between light and dark. Follows the system until the person chooses;
 * the label always names the mode the button will switch to.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const { resolvedTheme, setTheme } = useTheme();
  // True only after hydration, so the icon never disagrees with the server render.
  const mounted = React.useSyncExternalStore(
    subscribeNoop,
    () => true,
    () => false,
  );

  const isDark = mounted && resolvedTheme === "dark";
  const next = isDark ? "light" : "dark";

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className={className}
      aria-label={mounted ? `Switch to ${next} mode` : "Toggle colour mode"}
      data-testid="theme-toggle"
      onClick={() => setTheme(next)}
    >
      {isDark ? <SunMedium aria-hidden="true" /> : <MoonStar aria-hidden="true" />}
    </Button>
  );
}
