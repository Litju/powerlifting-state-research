import type { Layer } from "@/lib/story";

const DIM = 0.22;

/**
 * Static semantic diagram of the same conceptual picture as the 3D scene. It is the WebGL-off and reduced-motion
 * presentation and carries the full information as text (title, description, labels).
 */
export function Schematic({ focus, id }: { focus: Layer[]; id: string }) {
  const op = (l: Layer) => (focus.includes(l) ? 1 : DIM);
  const titleId = `${id}-t`;
  const descId = `${id}-d`;
  // Conceptual curves (not data): capacity rises, expression sits below it, assessments scatter around expression.
  const C = "M30,170 C110,160 170,110 300,80 S470,52 560,46";
  const E = "M30,186 C100,184 150,150 210,138 S260,128 300,112 S470,76 560,70";
  const Ctail = "M300,80 C380,64 470,52 560,46";
  const Cstop = "M300,80 C360,92 450,126 560,150";
  const ys = [
    [58, 182], [92, 180], [126, 168], [160, 158], [194, 142], [228, 150], [262, 128], [292, 118],
  ];
  return (
    <svg viewBox="0 0 600 240" role="img" aria-labelledby={`${titleId} ${descId}`} style={{ width: "100%", height: "auto", maxWidth: 760 }} data-testid="schematic">
      <title id={titleId}>Schematic of latent capacity C, expressed performance E, observed noisy Y and the information boundary</title>
      <desc id={descId}>
        Conceptual illustration, not measured data. Time runs left to right. Latent capacity C rises slowly. Expressed performance E lies below C because of a
        fast suppression state. Observed assessments Y scatter around E. A vertical plane marks the information boundary at day 223, with the forecast origin at day 224.
        To its right, C continues or falls depending on the plan, and future assessments are uncertain.
      </desc>
      <rect x="0" y="0" width="600" height="240" fill="#0c0e12" />
      <g stroke="#2b303a" strokeWidth="1">
        {[40, 80, 120, 160, 200].map((y) => (
          <line key={y} x1="20" x2="580" y1={y} y2={y} />
        ))}
      </g>
      <line x1="20" y1="214" x2="580" y2="214" stroke="#8d96a8" />
      <text x="580" y="230" textAnchor="end" fontSize="11" fill="#b3b8c2" fontFamily="ui-monospace, monospace">time (days)</text>
      <g opacity={op("gap")} stroke="#9aa3b5" strokeWidth="1">
        {[70, 130, 190, 250].map((x, i) => (
          <line key={x} x1={x} x2={x} y1={[161, 142, 118, 97][i]} y2={[181, 164, 140, 118][i]} />
        ))}
      </g>
      <path d={C} fill="none" stroke="#5ed3d9" strokeWidth="3" opacity={op("C")} />
      <path d={E} fill="none" stroke="#f2a65a" strokeWidth="3" opacity={op("E")} />
      <g fill="#bba8ff" opacity={op("Y")}>
        {ys.map(([x, y]) => (
          <circle key={x} cx={x} cy={y} r="4" />
        ))}
      </g>
      <g opacity={op("future")} fill="none" strokeWidth="2" strokeDasharray="6 5">
        <path d={Ctail} stroke="#5ed3d9" />
        <path d={Cstop} stroke="#5ed3d9" />
        {[340, 420, 520].map((x, i) => (
          <circle key={x} cx={x} cy={[96, 92, 84][i]} r="5" stroke="#bba8ff" />
        ))}
      </g>
      <g opacity={op("boundary")}>
        <line x1="300" x2="300" y1="20" y2="214" stroke="#ff8d84" strokeWidth="2" />
        <rect x="300" y="20" width="270" height="194" fill="#ff8d84" opacity="0.07" />
        <text x="294" y="34" textAnchor="end" fontSize="11" fill="#ff8d84" fontFamily="ui-monospace, monospace">history ends day 223</text>
        <text x="306" y="34" fontSize="11" fill="#ff8d84" fontFamily="ui-monospace, monospace">origin 224</text>
      </g>
      <g fontSize="12" fontFamily="ui-sans-serif, system-ui, sans-serif">
        <text x="34" y="150" fill="#5ed3d9" opacity={op("C")}>C latent capacity</text>
        <text x="34" y="205" fill="#f2a65a" opacity={op("E")}>E expressed</text>
        <text x="114" y="205" fill="#bba8ff" opacity={op("Y")}>Y observed (noisy)</text>
      </g>
    </svg>
  );
}
