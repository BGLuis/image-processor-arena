const LANGUAGES: Record<string, { label: string; color: string }> = {
  rust: { label: 'Rust', color: 'var(--lang-rust)' },
  go: { label: 'Go', color: 'var(--lang-go)' },
  cpp: { label: 'C++', color: 'var(--lang-cpp)' },
  python: { label: 'Python', color: 'var(--lang-python)' },
};

const ORDER = Object.keys(LANGUAGES);

export function langLabel(lang: string): string {
  return LANGUAGES[lang]?.label ?? lang;
}

export function langColor(lang: string): string {
  return LANGUAGES[lang]?.color ?? 'var(--arena-text-muted)';
}

/** Linguagens presentes nos dados, na ordem fixa da paleta (a cor segue a linguagem, nunca o rank). */
export function sortLanguages(langs: Iterable<string>): string[] {
  const rank = (l: string) => (ORDER.includes(l) ? ORDER.indexOf(l) : ORDER.length);
  return [...new Set(langs)].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
}
