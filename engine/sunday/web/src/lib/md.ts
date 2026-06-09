// Minimal, safe markdown → HTML (headings, fenced code, lists, bold, inline code, links).
// HTML is escaped before any transform, so rendering the server-controlled /manual via
// v-html cannot inject markup. Deliberately tiny — no parser dependency.

function esc(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function inline(s: string): string {
  return esc(s)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
}

export function renderMarkdown(src: string): string {
  const out: string[] = []
  let inCode = false
  let inList = false
  const closeList = () => { if (inList) { out.push('</ul>'); inList = false } }

  for (const raw of src.split('\n')) {
    if (raw.trimStart().startsWith('```')) {
      if (inCode) { out.push('</code></pre>'); inCode = false }
      else { closeList(); out.push('<pre><code>'); inCode = true }
      continue
    }
    if (inCode) { out.push(esc(raw)); continue }

    const h = raw.match(/^(#{1,4})\s+(.*)$/)
    if (h) { closeList(); out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`); continue }
    if (/^\s*[-*]\s+/.test(raw)) {
      if (!inList) { out.push('<ul>'); inList = true }
      out.push(`<li>${inline(raw.replace(/^\s*[-*]\s+/, ''))}</li>`)
      continue
    }
    if (raw.trim() === '') { closeList(); continue }
    closeList()
    out.push(`<p>${inline(raw)}</p>`)
  }
  if (inCode) out.push('</code></pre>')
  closeList()
  return out.join('\n')
}
