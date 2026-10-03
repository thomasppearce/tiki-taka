import { EventFeed } from "@/components/EventFeed";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center gap-8 px-6 py-12">
      <header className="w-full max-w-3xl">
        <h1 className="text-2xl font-semibold tracking-tight">Match Desk</h1>
        <p className="mt-1 text-sm text-zinc-400">
          Every graphic on air has receipts, and a human in the loop.
        </p>
      </header>
      <EventFeed />
    </main>
  );
}
