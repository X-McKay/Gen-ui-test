"use client";

import { useGenerativeUIAccessibility } from "@copilotkit/react-core/v2/generative-ui";
import { OctagonAlert } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";

export interface EscalationNoticeProps {
  title: string;
  reasons: string[];
  contact: string;
  onAcknowledge?: (args: Record<string, never>) => Promise<unknown>;
}

export function EscalationNotice({ title, reasons, contact, onAcknowledge }: EscalationNoticeProps) {
  const accessibility = useGenerativeUIAccessibility();
  const [acknowledged, setAcknowledged] = useState(false);
  return (
    <section
      {...accessibility}
      role="alert"
      data-testid="EscalationNotice"
      className="surface-enter grid gap-4 rounded-[var(--radius)] border p-6"
      style={{
        borderColor: "var(--tier-prohibited, #b42318)",
        background: "color-mix(in oklab, var(--tier-prohibited, #b42318) 8%, var(--card))",
      }}
    >
      <div className="flex items-start gap-3">
        <OctagonAlert
          className="mt-0.5 size-6 shrink-0"
          style={{ color: "var(--tier-prohibited, #b42318)" }}
          aria-hidden="true"
        />
        <div className="grid gap-1">
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="text-sm text-muted-foreground max-w-[70ch]">
            The EU AI Act prohibits this practice (Article 5). The intake stops here and goes to the governance team.
          </p>
        </div>
      </div>
      <ul className="grid gap-1.5 pl-9 text-sm list-disc max-w-[70ch]">
        {reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
      <p className="pl-9 text-sm font-medium">{contact}</p>
      <div className="pl-9">
        <Button
          type="button"
          className="h-11"
          disabled={acknowledged}
          data-testid="acknowledge-escalation"
          onClick={async () => {
            setAcknowledged(true);
            await onAcknowledge?.({});
          }}
        >
          {acknowledged ? "Acknowledged" : "I understand"}
        </Button>
      </div>
    </section>
  );
}
