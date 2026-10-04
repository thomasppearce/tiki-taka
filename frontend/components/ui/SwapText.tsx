"use client";

import {
  type ElementType,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

const SWAP_MS = 150; // --text-swap-dur

/**
 * Text that changes in place with the transitions.dev text-swap: the old copy exits up through a
 * small blur, then the new copy rises in. Phases: idle -> exit -> enter (no transition) -> idle.
 */
export function SwapText({
  text,
  as: Tag = "span",
  className = "",
}: {
  text: string;
  as?: ElementType;
  className?: string;
}) {
  const [target, setTarget] = useState(text);
  const [shown, setShown] = useState(text);
  const [phase, setPhase] = useState<"idle" | "exit" | "enter">("idle");
  const ref = useRef<HTMLElement>(null);

  // A new target text starts the exit (state adjusted during render, React's derived-state pattern).
  if (text !== target) {
    setTarget(text);
    setPhase("exit");
  }

  useEffect(() => {
    if (phase !== "exit") return;
    const timer = setTimeout(() => {
      setShown(target);
      setPhase("enter");
    }, SWAP_MS);
    return () => clearTimeout(timer);
  }, [phase, target]);

  useLayoutEffect(() => {
    if (phase !== "enter") return;
    void ref.current?.offsetHeight; // commit the enter-start position before releasing it
    const frame = requestAnimationFrame(() => setPhase("idle"));
    return () => cancelAnimationFrame(frame);
  }, [phase]);

  const state =
    phase === "exit" ? "is-exit" : phase === "enter" ? "is-enter-start" : "";
  return (
    <Tag ref={ref} className={`t-text-swap ${state} ${className}`}>
      {shown}
    </Tag>
  );
}
