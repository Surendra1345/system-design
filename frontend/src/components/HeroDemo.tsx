// A tiny looping picture of what the labs show: requests reach a load balancer, a server dies, traffic moves to the others.
export function HeroDemo() {
  const servers = [8, 86, 164];   // top edge of each server box
  return (
    <svg viewBox="0 0 560 230" className="herodemo" role="img" aria-label="Requests flowing through a load balancer to three servers. One server fails and the traffic moves to the other two.">
      <rect x={20} y={90} width={70} height={44} rx={10} fill="var(--surface)" stroke="var(--line)" />
      <text x={55} y={117} textAnchor="middle" fontSize="13" fill="var(--text)" fontWeight="700">Users</text>
      <rect x={190} y={90} width={90} height={44} rx={10} fill="var(--primary)" />
      <text x={235} y={117} textAnchor="middle" fontSize="13" fill="#fff" fontWeight="700">Balancer</text>
      <line x1={90} y1={112} x2={190} y2={112} stroke="var(--line)" strokeWidth="2" />
      {[0, 1, 2, 3].map(k => (
        <circle key={k} r="5" fill="var(--primary)">
          <animateMotion dur="1.6s" begin={`${k * 0.4}s`} repeatCount="indefinite" path="M90,112 L190,112" />
        </circle>
      ))}
      {servers.map((y, i) => (
        <g key={i}>
          <line x1={280} y1={112} x2={400} y2={y + 28} stroke="var(--line)" strokeWidth="2" />
          <rect x={400} y={y} width={120} height={56} rx={10} fill="var(--surface)" stroke="var(--line)" strokeWidth="2">
            {i === 1 && <animate attributeName="stroke" values="var(--line);var(--line);var(--danger);var(--danger);var(--line)" dur="8s" repeatCount="indefinite" />}
          </rect>
          <text x={460} y={y + 24} textAnchor="middle" fontSize="13" fill="var(--text)" fontWeight="700">Server {i + 1}</text>
          {i === 1 && <text x={460} y={y + 44} textAnchor="middle" fontSize="12" fill="var(--danger)" fontWeight="700"><animate attributeName="opacity" values="0;0;1;1;0" dur="8s" repeatCount="indefinite" />crashed: traffic rerouted</text>}
          {[0, 1].map(k => (
            <circle key={k} r="5" fill={i === 1 ? "var(--danger)" : "var(--success)"}>
              {i === 1 && <animate attributeName="opacity" values="1;1;0;0;1" dur="8s" repeatCount="indefinite" />}
              <animateMotion dur="1.6s" begin={`${k * 0.8 + i * 0.2}s`} repeatCount="indefinite" path={`M280,112 L400,${y + 28}`} />
            </circle>
          ))}
        </g>
      ))}
    </svg>
  );
}
