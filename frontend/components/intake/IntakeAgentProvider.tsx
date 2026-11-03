"use client";

import { CopilotKitProvider } from "@copilotkit/react-core/v2";
import type { ReactNode } from "react";

import { intakeUI } from "@/generative-ui/intakeCatalog";
import { AGENT_ID } from "@/lib/intakeState";

const enableInspector = process.env.NODE_ENV !== "production" && process.env.NEXT_PUBLIC_ENABLE_INSPECTOR !== "0";

/** Mounts the CopilotKit runtime connection and the intake catalog for one page. */
export function IntakeAgentProvider({ children }: { children: ReactNode }) {
  return (
    <CopilotKitProvider
      runtimeUrl="/api/copilotkit"
      agentId={AGENT_ID}
      generativeUI={{ ui: intakeUI }}
      enableInspector={enableInspector}
    >
      {children}
    </CopilotKitProvider>
  );
}
