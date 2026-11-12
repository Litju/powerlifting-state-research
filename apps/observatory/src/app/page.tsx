import { Story } from "@/components/story/Story";
import { evidence } from "@/lib/evidence";
import { buildStoryEvidence } from "@/lib/story-evidence";

// Computed at build time on the server: the client receives only the few aggregate values the story shows.
const storyEvidence = buildStoryEvidence(evidence);

export default function HomePage() {
  return <Story evidence={storyEvidence} />;
}
