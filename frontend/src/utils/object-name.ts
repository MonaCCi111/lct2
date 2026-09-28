/**
 * Display mapping for object names. The backend keeps sending "объект Альфа"; operators read the
 * letter itself, which is shorter, scans faster in a dense column and matches how the objects are
 * marked in the field. Raw names stay untouched in the domain, in filters values and in search —
 * `objectSearchText` keeps both spellings findable.
 */
const greekLetters: Record<string, string> = {
  Альфа: 'α',
  Бета: 'β',
  Вита: 'β',
  Гамма: 'γ',
  Дельта: 'δ',
  Эпсилон: 'ε',
  Дзета: 'ζ',
  Зета: 'ζ',
  Эта: 'η',
  Тета: 'θ',
  Фита: 'θ',
  Йота: 'ι',
  Каппа: 'κ',
  Лямбда: 'λ',
  Мю: 'μ',
  Ню: 'ν',
  Кси: 'ξ',
  Омикрон: 'ο',
  Пи: 'π',
  Ро: 'ρ',
  Сигма: 'σ',
  Тау: 'τ',
  Ипсилон: 'υ',
  Фи: 'φ',
  Хи: 'χ',
  Пси: 'ψ',
  Омега: 'Ω',
};
/** "объект Альфа" → "объект α"; anything without a known letter is returned unchanged. */
export function formatObjectName(name: string): string {
  const trimmed = name.trim();
  const separator = trimmed.lastIndexOf(' ');
  const letter = greekLetters[separator < 0 ? trimmed : trimmed.slice(separator + 1)];
  if (!letter) return name;
  return separator < 0 ? letter : `${trimmed.slice(0, separator)} ${letter}`;
}
/** Both spellings stay searchable, so an operator can type "Альфа" or "α". */
export function objectSearchText(name: string): string {
  const display = formatObjectName(name);
  return display === name ? name : `${name} ${display}`;
}
