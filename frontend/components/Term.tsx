"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { GLOSSARY, type GlossaryKey } from "@/lib/glossary";

/**
 * A word with a plain-English definition: <Term k="kwh" /> or <Term k="kwh">units</Term>.
 *
 * Accessible "toggletip": the word is a button. Tap, click, or press Enter/Space to
 * show the definition; Escape, tapping elsewhere or moving focus away hides it.
 * Hovering with a mouse also shows it. Screen readers hear the definition as the
 * button's description when it opens.
 */
export default function Term({ k, children }: { k: GlossaryKey; children?: React.ReactNode }) {
  const entry = GLOSSARY[k];
  const [open, setOpen] = useState(false);
  const id = useId();
  const wrap = useRef<HTMLSpanElement>(null);
  const tip = useRef<HTMLSpanElement>(null);
  // Opened by a mouse hover: the click that usually follows should keep it open, not close it.
  const hoverOpened = useRef(false);
  const [shift, setShift] = useState(0);

  // Keep the definition on screen: centred under the word, nudged sideways near the edges.
  useLayoutEffect(() => {
    if (!open || !tip.current) return;
    const GUTTER = 16;
    const r = tip.current.getBoundingClientRect();
    const left = r.left - shift;             // where it sits when centred
    const right = left + r.width;
    const vw = document.documentElement.clientWidth;
    let dx = 0;
    if (left < GUTTER) dx = GUTTER - left;
    else if (right > vw - GUTTER) dx = vw - GUTTER - right;
    if (Math.round(dx) !== Math.round(shift)) setShift(dx);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const onDown = (e: PointerEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onDown);
    };
  }, [open]);

  return (
    <span
      ref={wrap}
      className="relative inline-block"
      onPointerEnter={(e) => {
        if (e.pointerType === "mouse" && !open) { hoverOpened.current = true; setOpen(true); }
      }}
      onPointerLeave={(e) => {
        if (e.pointerType === "mouse" && hoverOpened.current) { hoverOpened.current = false; setOpen(false); }
      }}
      onBlur={(e) => !e.currentTarget.contains(e.relatedTarget as Node) && setOpen(false)}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-describedby={open ? id : undefined}
        onClick={() => {
          if (hoverOpened.current) { hoverOpened.current = false; setOpen(true); }   // pin it open
          else setOpen((v) => !v);
        }}
        className="underline decoration-dotted decoration-2 underline-offset-4 decoration-[#f97316] hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#f97316] rounded-sm cursor-help"
      >
        {children ?? entry.label}
        <span className="sr-only"> (what does this mean?)</span>
      </button>
      <span
        ref={tip}
        id={id}
        role="tooltip"
        hidden={!open}
        style={{ transform: `translateX(calc(-50% + ${shift}px))` }}
        className="absolute left-1/2 top-full z-20 mt-2 w-64 max-w-[calc(100vw-2rem)] rounded-lg border border-slate-600 bg-[#13233d] p-3 text-left text-sm font-normal leading-snug text-slate-100 shadow-xl"
      >
        <strong className="block text-white">{entry.label}</strong>
        {entry.definition}
      </span>
    </span>
  );
}
