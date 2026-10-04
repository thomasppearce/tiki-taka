import { MatchPage } from "@/components/match/MatchPage";

// The matchday is always 3 leagues x 4 fixtures, so every match page is generated at build time
// (the app ships as a static export).
export const dynamicParams = false;

export function generateStaticParams(): { id: string }[] {
  return [1, 2, 3].flatMap((league) =>
    [1, 2, 3, 4].map((fixture) => ({ id: `m_l${league}_${fixture}` })),
  );
}

export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <MatchPage matchId={id} />;
}
