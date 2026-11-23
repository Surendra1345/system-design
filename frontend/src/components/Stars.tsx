export function Stars({ n, big }: { n: number; big?: boolean }) {
  return (
    <span className="stars" style={big ? { fontSize: 40 } : undefined} aria-label={`${n} of 3 stars`}>
      {"★".repeat(n)}<span className="off">{"★".repeat(3 - n)}</span>
    </span>
  );
}
