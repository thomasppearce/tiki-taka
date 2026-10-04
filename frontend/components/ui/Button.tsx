import type { ButtonHTMLAttributes, ReactNode } from "react";

import { Kbd } from "@/components/ui/Kbd";

type Variant = "primary" | "ghost";

const VARIANTS: Record<Variant, string> = {
  primary:
    "border-air bg-air text-ink-on-fill hover:border-air-hover hover:bg-air-hover",
  ghost:
    "border-line text-ink-2 hover:border-line-strong hover:bg-raised hover:text-ink",
};

/** Console button with an optional keyboard shortcut hint. */
export function Button({
  variant = "ghost",
  shortcut,
  children,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  shortcut?: string;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      className={`inline-flex h-7 items-center gap-1.5 rounded-md border px-2 text-label font-medium transition-[background-color,border-color,color,transform] duration-150 ease-out focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-air active:translate-y-px disabled:pointer-events-none disabled:opacity-50 ${VARIANTS[variant]} ${className}`}
      {...props}
    >
      {children}
      {shortcut && <Kbd onFill={variant === "primary"}>{shortcut}</Kbd>}
    </button>
  );
}
