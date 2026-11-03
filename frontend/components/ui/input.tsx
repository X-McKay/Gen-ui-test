import * as React from "react";
import { Input as InputPrimitive } from "@base-ui/react/input";

import { cn } from "@/lib/utils";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <InputPrimitive
      type={type}
      data-slot="input"
      className={cn(
        "h-11 w-full min-w-0 rounded-lg border border-input bg-card px-3 py-2 text-base text-foreground shadow-1 transition-[border-color,box-shadow] duration-150 outline-none placeholder:text-muted-foreground/80 hover:border-[color-mix(in_oklch,var(--input),var(--foreground)_20%)] focus-visible:border-ring focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60 aria-invalid:border-destructive aria-invalid:focus-visible:outline-destructive md:text-sm",
        className,
      )}
      {...props}
    />
  );
}

export { Input };
