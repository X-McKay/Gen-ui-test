import * as React from "react";

import { cn } from "@/lib/utils";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex min-h-24 w-full rounded-lg border border-input bg-card px-3 py-2.5 text-base text-foreground shadow-1 transition-[border-color,box-shadow] duration-150 outline-none field-sizing-content placeholder:text-muted-foreground/80 hover:border-[color-mix(in_oklch,var(--input),var(--foreground)_20%)] focus-visible:border-ring focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60 aria-invalid:border-destructive aria-invalid:focus-visible:outline-destructive md:text-sm",
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
