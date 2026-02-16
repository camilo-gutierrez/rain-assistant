"use client";

import { isSecureContext } from "@/lib/constants";

export default function SecurityBanner() {
  if (typeof window === "undefined" || isSecureContext()) return null;

  return (
    <div className="w-full bg-yellow-500/15 border-b border-yellow-500/40 px-4 py-2 text-center text-sm text-yellow-400">
      <span className="mr-1">&#9888;</span>
      Connection is not secure (HTTP). Your PIN and data may be intercepted.
    </div>
  );
}
