// Split rendered text only at references backed by an available evidence record.
export function citationParts(value, evidence) {
  const content = String(value || '').replace(/\*\*/g, '');
  if (!evidence || !evidence.length) return [{ text: content }];

  const byIndex = new Map(evidence.map(fact => [Number(fact.index), fact]));
  return content.split(/(\[\d+\])/g).filter(Boolean).map(part => {
    const match = part.match(/^\[(\d+)\]$/);
    const fact = match && byIndex.get(Number(match[1]));
    return fact ? { fact } : { text: part };
  });
}

export function isSourceLink(url) {
  return typeof url === 'string' && /^https?:\/\/[^\s]+$/i.test(url);
}
