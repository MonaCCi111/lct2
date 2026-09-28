import { describe, expect, it } from 'vitest';
import { formatObjectName, objectSearchText } from './object-name';
import { healthIndexTone, probabilityTone } from './metric-tone';

describe('object display names', () => {
  it.each([
    ['объект Альфа', 'объект α'],
    ['объект Бета', 'объект β'],
    ['объект Гамма', 'объект γ'],
    ['объект Дельта', 'объект δ'],
    ['объект Кси', 'объект ξ'],
    ['объект Тау', 'объект τ'],
    ['объект Фита', 'объект θ'],
    ['объект Омега', 'объект Ω'],
  ])('renders %s as %s', (raw, display) => {
    expect(formatObjectName(raw)).toBe(display);
  });
  it('leaves names without a known letter untouched', () => {
    for (const name of ['Тяговая подстанция 4', 'объект 12', 'Альфа-2', ''])
      expect(formatObjectName(name)).toBe(name);
  });
  it('keeps both spellings searchable', () => {
    expect(objectSearchText('объект Фита')).toBe('объект Фита объект θ');
    expect(objectSearchText('Тяговая подстанция 4')).toBe('Тяговая подстанция 4');
  });
});

describe('metric tones', () => {
  it('scales probability by its own value, never by risk', () => {
    expect(probabilityTone(0.82)).toBe('critical');
    expect(probabilityTone(0.8)).toBe('critical');
    expect(probabilityTone(0.71)).toBe('high');
    // The 46% critical prediction keeps its own scale; the risk column stays backend-supplied.
    expect(probabilityTone(0.46)).toBe('medium');
    expect(probabilityTone(0.12)).toBeNull();
  });
  it('treats a low ИТС as the worrying end of the scale', () => {
    expect(healthIndexTone(19)).toBe('critical');
    expect(healthIndexTone(42)).toBe('high');
    expect(healthIndexTone(65)).toBe('medium');
    expect(healthIndexTone(88)).toBeNull();
  });
  it('never invents a tone for missing or broken values', () => {
    for (const value of [null, Number.NaN, Infinity]) {
      expect(probabilityTone(value)).toBeNull();
      expect(healthIndexTone(value)).toBeNull();
    }
  });
});
