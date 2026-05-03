import { Suspense } from "react";
import HomeClient from "./ui/HomeClient";

export default function Page() {
  return (
    <Suspense fallback={<div className="shell" style={{ padding: 24 }}>Loading…</div>}>
      <HomeClient />
    </Suspense>
  );
}
