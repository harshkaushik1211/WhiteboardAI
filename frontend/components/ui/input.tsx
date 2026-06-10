import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "flex h-12 w-full rounded-lg border border-white/20 bg-white/5 px-4 py-2 text-base text-white placeholder:text-white/40 focus:outline-none focus:ring-2 focus:ring-brand-500",
      className
    )}
    {...props}
  />
));
Input.displayName = "Input";
