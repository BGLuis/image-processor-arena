'use client';

import React from 'react';
import { Trophy, Terminal, Sun, Moon, Monitor } from 'lucide-react';
import { useData } from '../context/DataContext';
import { useTheme } from '../context/ThemeContext';

export default function TopBar() {
  const { isDbReady, initError, languages, totalImplementations } = useData();
  const { theme, setTheme } = useTheme();

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const navItems = [
    { id: 'podium', label: '01 Pódio' },
    { id: 'duel', label: '02 Duelo' },
    { id: 'tradeoffs', label: '03 Trade-offs' },
    { id: 'ranking', label: '04 Ranking' },
    { id: 'matrix', label: '05 Matriz' },
    { id: 'sql', label: '06 SQL' },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b border-[var(--arena-border)] bg-[var(--arena-canvas)]/90 backdrop-blur-md transition-colors">
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        
        {/* Brand */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="w-8 h-8 rounded-lg bg-[var(--arena-surface)] border border-[#C9501C]/40 dark:border-[#E0703A]/40 flex items-center justify-center text-[#C9501C] dark:text-[#E0703A] shadow-sm">
            <Trophy className="w-4 h-4" />
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center sm:gap-2.5">
            <div className="flex items-center gap-2">
              <span className="text-sm sm:text-base font-bold tracking-tight text-[var(--arena-text-primary)]">
                Image Processor Arena
              </span>
              <span className="hidden xl:inline-block text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded bg-[var(--arena-surface)] border border-[var(--arena-border)] text-[var(--arena-text-secondary)]">
                v2 · Cronometragem
              </span>
            </div>

            {/* Language dots */}
            <div className="hidden sm:flex items-center gap-1.5 pl-1 text-[var(--arena-text-secondary)] text-xs">
              <span className="w-2 h-2 rounded-full bg-[#0086A3] dark:bg-[#25A3B5]" title="Go" />
              <span className="w-2 h-2 rounded-full bg-[#C9501C] dark:bg-[#E0703A]" title="Rust" />
              <span className="w-2 h-2 rounded-full bg-[var(--lang-cpp)]" title="C++" />
              <span className="w-2 h-2 rounded-full bg-[var(--lang-python)]" title="Python" />
              <span className="ml-1 text-[11px] font-mono text-[var(--arena-text-muted)]">
                {languages.length} linguagens · {totalImplementations} implementações
              </span>
            </div>
          </div>
        </div>

        {/* Section Navigation Anchors */}
        <nav className="hidden lg:flex items-center gap-1 text-xs font-mono">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => scrollToSection(item.id)}
              className="px-2.5 py-1 rounded-md text-[var(--arena-text-secondary)] hover:text-[var(--arena-text-primary)] hover:bg-[var(--arena-surface)] transition-colors cursor-pointer"
            >
              {item.label}
            </button>
          ))}
        </nav>

        {/* Status, Theme Switcher & SQL */}
        <div className="flex items-center gap-2.5 sm:gap-3 text-xs shrink-0">
          
          {/* DuckDB Status */}
          <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[var(--arena-surface)] border border-[var(--arena-border)]">
            <span className={`w-1.5 h-1.5 rounded-full ${
              isDbReady ? 'bg-[#2E8B3E] dark:bg-[#3DD68C] shadow-[0_0_8px_#3DD68C]' : initError ? 'bg-[#C9501C] dark:bg-[#F2546B]' : 'bg-[#9A7B00] dark:bg-[#F5A524] animate-pulse'
            }`} />
            <span className="text-[11px] font-mono text-[var(--arena-text-secondary)]">
              {isDbReady ? 'DuckDB-Wasm' : initError ? 'DuckDB offline' : 'Iniciando...'}
            </span>
          </div>

          {/* 3-way Theme Switcher (Claro / Escuro / Sistema) */}
          <div className="flex items-center p-0.5 rounded-lg bg-[var(--arena-surface)] border border-[var(--arena-border)] text-[var(--arena-text-secondary)]">
            <button
              onClick={() => setTheme('light')}
              title="Tema Claro"
              className={`p-1.5 rounded-md transition-all cursor-pointer ${
                theme === 'light'
                  ? 'bg-[var(--arena-raised)] text-[var(--arena-text-primary)] shadow-xs font-medium'
                  : 'hover:text-[var(--arena-text-primary)]'
              }`}
            >
              <Sun className="w-3.5 h-3.5" />
              <span className="sr-only">Claro</span>
            </button>

            <button
              onClick={() => setTheme('dark')}
              title="Tema Escuro"
              className={`p-1.5 rounded-md transition-all cursor-pointer ${
                theme === 'dark'
                  ? 'bg-[var(--arena-raised)] text-[var(--arena-text-primary)] shadow-xs font-medium'
                  : 'hover:text-[var(--arena-text-primary)]'
              }`}
            >
              <Moon className="w-3.5 h-3.5" />
              <span className="sr-only">Escuro</span>
            </button>

            <button
              onClick={() => setTheme('system')}
              title="Tema do Sistema"
              className={`p-1.5 rounded-md transition-all cursor-pointer ${
                theme === 'system'
                  ? 'bg-[var(--arena-raised)] text-[var(--arena-text-primary)] shadow-xs font-medium'
                  : 'hover:text-[var(--arena-text-primary)]'
              }`}
            >
              <Monitor className="w-3.5 h-3.5" />
              <span className="sr-only">Sistema</span>
            </button>
          </div>

          {/* Quick SQL Console Button */}
          <button
            onClick={() => scrollToSection('sql')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[var(--arena-surface)] hover:bg-[var(--arena-raised)] border border-[var(--arena-border)] hover:border-[var(--arena-border-strong)] text-[var(--arena-text-primary)] transition-colors cursor-pointer text-xs font-medium"
          >
            <Terminal className="w-3.5 h-3.5 text-[#2E8B3E] dark:text-[#3DD68C]" />
            <span className="hidden sm:inline font-mono">SQL</span>
          </button>
        </div>

      </div>
    </header>
  );
}
