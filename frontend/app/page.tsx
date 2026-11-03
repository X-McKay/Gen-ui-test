import type { Metadata } from "next";
import { FilePlus2, GitBranch } from "lucide-react";

import { ModeSelectionCard } from "@/components/landing/ModeSelectionCard";

export const metadata: Metadata = {
  title: "AI Governance Intake",
};

export default function Home() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-12 md:px-6 md:py-16">
      <section
        className="surface-enter flex w-full max-w-[880px] flex-col items-center"
        aria-labelledby="landing-title"
      >
        <h1
          id="landing-title"
          className="max-w-[28ch] text-center text-[1.75rem] leading-[1.15] font-medium tracking-[-0.02em] text-balance md:text-xl"
        >
          Bring a project into AI governance
        </h1>
        <p className="mt-4 max-w-[48ch] text-center text-base text-muted-foreground text-pretty md:text-[1.0625rem] md:leading-7">
          Describe it or point us at the repository. We infer what we can, confirm it with you, and classify it in
          minutes.
        </p>

        <nav aria-label="Choose how to start" className="mt-10 w-full md:mt-14">
          <ul className="grid grid-cols-1 gap-4 md:grid-cols-2 md:gap-6">
            <li className="flex">
              <ModeSelectionCard
                href="/intake/new"
                title="New project"
                description="Describe the project and answer a handful of questions."
                icon={FilePlus2}
                testId="mode-card-new"
                className="flex-1"
              />
            </li>
            <li className="flex">
              <ModeSelectionCard
                href="/intake/existing"
                title="Existing project"
                description="Point us at a repository and confirm what we find."
                icon={GitBranch}
                testId="mode-card-existing"
                className="flex-1"
              />
            </li>
          </ul>
        </nav>
      </section>
    </div>
  );
}
