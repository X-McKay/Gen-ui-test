import { Button as ButtonPrimitive } from "@base-ui/react/button";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center rounded-lg border border-transparent text-sm font-medium whitespace-nowrap transition-[background-color,color,border-color,box-shadow,transform] duration-150 outline-none select-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring active:not-aria-[haspopup]:translate-y-px disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow-1 hover:bg-[color-mix(in_oklch,var(--primary),black_8%)] dark:hover:bg-[color-mix(in_oklch,var(--primary),white_8%)]",
        outline:
          "border-border bg-card text-foreground shadow-1 hover:bg-muted aria-expanded:bg-muted",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-[color-mix(in_oklch,var(--secondary),var(--foreground)_6%)] aria-expanded:bg-secondary",
        ghost:
          "text-foreground hover:bg-muted aria-expanded:bg-muted dark:hover:bg-muted/70",
        destructive:
          "bg-destructive/10 text-destructive hover:bg-destructive/20 focus-visible:outline-destructive dark:bg-destructive/15 dark:hover:bg-destructive/25",
        accent:
          "bg-accent-soft text-accent-soft-foreground hover:bg-[color-mix(in_oklch,var(--accent-soft),var(--accent)_12%)]",
        link: "text-accent underline-offset-4 hover:underline",
      },
      size: {
        default: "h-11 gap-2 px-4",
        sm: "h-10 gap-1.5 px-3 text-sm",
        xs: "h-8 gap-1 rounded-md px-2.5 text-sm [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-12 gap-2 px-5 text-base",
        icon: "size-11",
        "icon-sm": "size-10",
        "icon-xs": "size-8 rounded-md [&_svg:not([class*='size-'])]:size-3.5",
        "icon-lg": "size-12",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}

export { Button, buttonVariants };
