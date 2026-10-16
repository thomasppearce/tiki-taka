# Demo video: script and shot list

Under 2 minutes (aim for 1:50). Record on the deployed site (production builds hide the Next.js
dev badge), in a 1440×900 browser window, dark theme. No music with rights attached; captions or a
voice-over carry the words. No real league, club, or broadcaster names or marks anywhere.

The judges' first pass is pass/fail on theme and on Microsoft Foundry and Agent Framework being
obvious, so both are on screen in the first 15 seconds, and the multi-agent story is told by
showing the agents at work, not by describing them.

## Before recording

- Open the producer view of the channel (role switch, top right). The *Match clock* row in the cut
  controls jumps the one shared clock: type a minute and press *Jump*. Everyone watching moves
  with it, so record when nobody else is using the site.
- Moments worth having on tape (matchday 38, seed fixed, the same every time):
  - **75:10** The checker sends the Director's answer back ("Nothing in the table is at stake in
    this match… but the cut talks about it"); the corrected cut follows. Jump to 74.9 and scroll
    to *The crew* about 15 seconds later.
  - **78:15–79'** The Director's countdown (78:15), the cut to Brackenford v Halvern (78:20),
    and Ambrose's goal (78:42): Halvern Town go top on goal difference. The Goal lower third
    follows at about 78:46 and the replay at about 78:51.
  - **92'** Ashby completes Ironvale's comeback: Porthallow into the top four, Tidewick out.
  - **93'** Desai's winner at Northgate: Westmere climb out of the drop, Corrin Bay go down, and
    Desai takes the Golden Boot lead.
- Jump to a minute or two before a moment, then let it play: the Director's countdown and the cut
  happen live.

## Scenes

| Time | Scene | On screen (setup) | Words (caption or voice) |
|---|---|---|---|
| 0:00–0:08 | **Cold open** | The channel at 91' (Guest; *Jump* to 91 first as producer), browser zoom 90% so the ten live scores are in shot: the multiview, the table | "The last day of the season. Ten matches at once. Where do you look?" |
| 0:08–0:15 | **Title** | Title card over the channel: *Tiki-Taka* · "A whip-around for every matchday, directed by AI agents on **Microsoft Foundry**, built with **Microsoft Agent Framework**" | (the card says it) |
| 0:15–0:32 | **A cut that explains itself** | Producer view, *Jump* to 78 (countdown 15 s later). The Director proposes a cut with a 5-second countdown; it takes it; Ambrose scores; the stinger, *Why we're here*, *At stake*, the table rows move | "A Watcher agent follows every match. A Director agent decides where to cut, weighing who's pushing against what a goal would change, and says why." |
| 0:32–0:42 | **Under the hood** | A separate take: *Jump* to 74.9; at about 75:12 scroll to *The crew* (under the ten matches): Signals propose a cut, the **Checker** sends the Director's answer back, the corrected cut goes on air | "Every sentence cites the events behind it. Code checks it before it airs; anything it can't verify goes back." |
| 0:42–0:58 | **Your channel** | `/split` at 92' (*Jump* to 92 first): a Westmere fan and a Corrin Bay fan side by side as Desai scores at 93' | "Sign in, pick your club or your fantasy XI, and the channel becomes yours. Same goal. One fan stays up. One goes down." |
| 0:58–1:15 | **The graphics desk** | Producer, featured match's control room (*Back to 55'* first, or any minute): a proposal card, select it, its receipts light up on the pitch and timeline; press **A**; the lower third animates in; switch the feed to Casual ES | "On the featured match, a team of agents drafts the graphics: an Interpreter, an Explainer with a Foundry IQ knowledge base, a fact-checker. A human producer approves every one." |
| 1:15–1:28 | **When an agent fails** | Control room: *Failure drill* → Explainer → *Take it down*; cut to the next moment (about two minutes later): Explainer **Down**, the others **Skipped**, the scripted graphic still queued on time | "Every model call gets a retry. When an agent is down, the system falls back on time, and says so." |
| 1:28–1:42 | **Proof** | Foundry portal: *Build › Agents*, the eight `tiki-taka-*` agents; open `tiki-taka-explainer` › *Traces*, one moment's trace (workflow → each agent → the knowledge base); then the whip-around eval table from `docs/evals/README.md` (or the Oct 15 runs under *Build › Evaluations*; blur *Created by*) | "Every run is traced in Foundry. Measured against one agent watching all ten matches: on the fast model it aired errors on a third of cuts; on the careful one it never made the countdown. The team did both." |
| 1:42–1:52 | **Full time** | Producer: *Skip to the final whistle*; the matchday recap: "Desai's goal decided survival and the Golden Boot", the match recaps on the multiview | "At the final whistle, the agents write how the day unfolded, every beat with its receipts." |
| 1:52–1:58 | **Close** | Card: *Tiki-Taka* · the URL · "Microsoft Foundry · Microsoft Agent Framework · Azure AI Search · Azure Container Apps" | "Every match. Every cut explained." |

## Notes

- The graphics eval (0 unsupported graphics on air for the team, 5 for one agent) is the backup
  proof line if the whip-around table reads too dense on screen.
- If a scene runs long, cut *Under the hood* first: the crew panel also appears in *Proof*.
- The failure drill's fallback only shows at the next moment; cut the wait.
