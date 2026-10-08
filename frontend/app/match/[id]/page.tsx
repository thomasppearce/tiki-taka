import { MatchPage } from "@/components/match/MatchPage";

// The final day is always ten fixtures, so every match page is generated at build time (the app
// ships as a static export).
export const dynamicParams = false;

export function generateStaticParams(): { id: string }[] {
  return Array.from({ length: 10 }, (_, i) => ({ id: `m_l1_${i + 1}` }));
}

export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <MatchPage matchId={id} />;
}
