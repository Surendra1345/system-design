// Lesson bodies are authored by us and stored in the repository. They are never user input.
export function Html({ html, className }: { html: string; className?: string }) {
  return <div className={className} dangerouslySetInnerHTML={{ __html: html }} />;
}
