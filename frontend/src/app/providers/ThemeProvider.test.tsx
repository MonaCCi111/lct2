import { readFileSync } from 'node:fs';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider, useTheme } from './ThemeProvider';

const bootstrap = readFileSync('public/theme-init.js', 'utf8');
let dark = false;
let listeners: Set<() => void>;
function Probe() {
  const theme = useTheme();
  return (
    <>
      <output>
        {theme.preference}/{theme.resolvedTheme}
      </output>
      {(['light', 'dark', 'system'] as const).map((value) => (
        <button key={value} onClick={() => theme.setPreference(value)}>
          {value}
        </button>
      ))}
    </>
  );
}
function mount() {
  window.eval(bootstrap);
  return render(
    <ThemeProvider>
      <Probe />
    </ThemeProvider>,
  );
}
function changeOs(value: boolean) {
  act(() => {
    dark = value;
    listeners.forEach((listener) => listener());
  });
}
beforeEach(() => {
  localStorage.clear();
  dark = false;
  listeners = new Set();
  vi.stubGlobal('matchMedia', () => ({
    get matches() {
      return dark;
    },
    addEventListener: (_: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_: string, listener: () => void) => listeners.delete(listener),
  }));
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
describe('Theme system and shared pre-paint bootstrap', () => {
  it('defaults to system and applies the OS theme before React mounts', () => {
    dark = true;
    window.eval(bootstrap);
    expect(document.documentElement.dataset.theme).toBe('dark');
    mount();
    expect(screen.getByRole('status')).toHaveTextContent('system/dark');
  });
  it.each(['light', 'dark'] as const)('persists and restores explicit %s', (value) => {
    const view = mount();
    fireEvent.click(screen.getByText(value, { selector: 'button' }));
    expect(localStorage.getItem('dolos-theme')).toBe(value);
    expect(document.documentElement.dataset.theme).toBe(value);
    changeOs(true);
    changeOs(false);
    expect(document.documentElement.dataset.theme).toBe(value);
    view.unmount();
    mount();
    expect(screen.getByRole('status')).toHaveTextContent(`${value}/${value}`);
  });
  it('follows runtime OS changes and stores system instead of the resolved theme', () => {
    const view = mount();
    changeOs(true);
    expect(document.documentElement.dataset.theme).toBe('dark');
    fireEvent.click(screen.getByText('light', { selector: 'button' }));
    fireEvent.click(screen.getByText('system', { selector: 'button' }));
    expect(localStorage.getItem('dolos-theme')).toBe('system');
    expect(document.documentElement.dataset.theme).toBe('dark');
    changeOs(false);
    expect(document.documentElement.dataset.theme).toBe('light');
    view.unmount();
    expect(listeners.size).toBe(0);
  });
  it.each([null, 'corrupt', '"dark"', 'system'])('safely restores %s as system', (value) => {
    if (value !== null) localStorage.setItem('dolos-theme', value);
    mount();
    expect(screen.getByRole('status')).toHaveTextContent('system/light');
  });
  it('works when storage reads and writes throw', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    mount();
    expect(screen.getByRole('status')).toHaveTextContent('system/light');
    fireEvent.click(screen.getByText('dark', { selector: 'button' }));
    expect(document.documentElement.dataset.theme).toBe('dark');
  });
});
