"use client";

import { useEffect } from "react";
import { warmUp } from "@/lib/api";

/** Wakes the API as soon as someone starts the journey, so the answer comes back quicker. */
export default function WarmUp() {
  useEffect(() => warmUp(), []);
  return null;
}
