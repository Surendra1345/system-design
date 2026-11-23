import type { ReactNode } from "react";

/** A tiny Markdown renderer for AI answers: headings, bullets, checklists, bold and code. No raw HTML is ever inserted. */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={i}>{part.slice(1, -1)}</code>;
    return part;
  });
}

export function Markdown({ text }: { text: string }) {
  const out: ReactNode[] = [];
  let list: ReactNode[] = [];
  const flush = (key: number) => { if (list.length) { out.push(<ul key={"ul" + key}>{list}</ul>); list = []; } };
  text.split("\n").forEach((raw, i) => {
    const line = raw.trimEnd();
    const bullet = /^\s*[-*]\s+(\[[ xX]\]\s+)?(.*)$/.exec(line);
    if (bullet) {
      list.push(<li key={i}>{bullet[1] ? <label className="chk"><input type="checkbox" /> <span>{inline(bullet[2])}</span></label> : inline(bullet[2])}</li>);
      return;
    }
    flush(i);
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    if (h) out.push(h[1].length <= 2 ? <h3 key={i}>{inline(h[2])}</h3> : <h4 key={i}>{inline(h[2])}</h4>);
    else if (line.trim()) out.push(<p key={i}>{inline(line)}</p>);
  });
  flush(-1);
  return <div className="md">{out}</div>;
}
