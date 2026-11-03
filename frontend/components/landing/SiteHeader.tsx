import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { Wordmark } from "@/components/landing/Wordmark";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-hairline bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex h-14 w-full max-w-[1200px] items-center justify-between px-4 md:px-6">
        <Wordmark />
        <ThemeToggle />
      </div>
    </header>
  );
}
