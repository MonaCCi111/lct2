import { createContext, useContext, useEffect, useLayoutEffect, useState, type ReactNode } from 'react';

export type ThemePreference = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';
interface ThemeContextValue {
  preference: ThemePreference;
  resolvedTheme: ResolvedTheme;
  setPreference: (theme: ThemePreference) => void;
}
declare global {
  interface Window {
    dolosTheme: {
      read: () => ThemePreference;
      resolve: (preference: ThemePreference) => ResolvedTheme;
      apply: (theme: ResolvedTheme) => void;
      save: (preference: ThemePreference) => void;
      media: string;
    };
  }
}
const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const runtime = window.dolosTheme;
  const [preference, updatePreference] = useState(runtime.read);
  const [systemTheme, setSystemTheme] = useState(() => runtime.resolve('system'));
  const resolvedTheme = preference === 'system' ? systemTheme : preference;
  useLayoutEffect(() => runtime.apply(resolvedTheme), [runtime, resolvedTheme]);
  useEffect(() => {
    const media = matchMedia(runtime.media);
    const update = () => setSystemTheme(media.matches ? 'dark' : 'light');
    media.addEventListener('change', update);
    update();
    return () => media.removeEventListener('change', update);
  }, [runtime]);
  const setPreference = (value: ThemePreference) => {
    runtime.save(value);
    updatePreference(value);
  };
  return (
    <ThemeContext.Provider value={{ preference, resolvedTheme, setPreference }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const value = useContext(ThemeContext);
  if (!value) throw new Error('useTheme requires ThemeProvider');
  return value;
}
