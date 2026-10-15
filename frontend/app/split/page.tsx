import { Suspense } from "react";

import { SplitPage } from "@/components/split/SplitPage";

// Two fans' channels side by side, on the same clock: /split?a=<club_id>&b=<club_id>.
// The clubs come from the URL, which a static page can only read in the browser (Suspense).
export default function Page() {
  return (
    <Suspense fallback={null}>
      <SplitPage />
    </Suspense>
  );
}
