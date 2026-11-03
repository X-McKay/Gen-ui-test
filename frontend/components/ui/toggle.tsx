"use client";

import { Toggle as TogglePrimitive } from "@base-ui/react/toggle";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const toggleVariants = cva(
  "group/toggle inline-flex items-center justify-center gap-1.5 rounded-lg border text-sm font-medium whitespace-nowrap transition-[background-color,color,border-color,box-shadow] duration-150 outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive aria-pressed:border-accent aria-pressed:bg-accent-soft aria-pressed:text-accent-soft-foreground data-[pressed]:border-accent data-[pressed]:bg-accent-soft data-[pressed]:text-accent-soft-foreground [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "border-transparent bg-transparent text-foreground hover:bg-muted",
        outline: "border-border bg-card text-foreground shadow-1 hover:bg-muted",
      },
      size: {
        default: "h-11 min-w-11 px-4",
        sm: "h-10 min-w-10 px-3 text-sm",
        lg: "h-12 min-w-12 px-5",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

function Toggle({
  className,
  variant = "default",
  size = "default",
  ...props
}: TogglePrimitive.Props & VariantProps<typeof toggleVariants>) {
  return (
    <TogglePrimitive
      data-slot="toggle"
      className={cn(toggleVariants({ variant, size, className }))}
      {...props}
    />
  );
}

export { Toggle, toggleVariants };
