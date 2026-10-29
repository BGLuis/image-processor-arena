'use client';

import React from 'react';
import { Trophy, Terminal } from 'lucide-react';
import { useData } from '../context/DataContext';

export default function TopBar() {
  const { isDbReady, initError } = useData();

  const scrollToConsole = () => {
    const el = document.getElementById('sql-console');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-[#222831] bg-[#0a0c0f]/90 backdrop-blur-md">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[#312c20] border border-[#816b33] flex items-center justify-center text-[#f2c14e] shadow-sm">
            <Trophy className="w-4 h-4" />
          </div>

          <div className="flex items-center gap-2.5">
            <h1 className="text-base sm:text-lg font-semibold tracking-tight text-[#eceff3]">
              Image Processor Arena
            </h1>

            <div className="hidden sm:block w-px h-4 bg-[#222831]" />

            {/* Language dots */}
            <div className="hidden sm:flex items-center gap-1.5 pl-1">
              <span className="w-2 h-2 rounded-full bg-[#2ec4e6]" title="Go" />
              <span className="w-2 h-2 rounded-full bg-[#f4743b]" title="Rust" />
              <span className="w-2 h-2 rounded-full bg-[#f7c548]" title="Zig" />
              <span className="w-2 h-2 rounded-full bg-[#e8618c]" title="Java" />
              <span className="w-2 h-2 rounded-full bg-[#8b7cf6]" title="C#" />
              <span className="w-2 h-2 rounded-full bg-[#a3e635]" title="Swift" />
              <span className="ml-1 text-xs text-[#a3acb9] font-normal">
                6 linguagens · 18 implementações
              </span>
            </div>
          </div>
        </div>

        {/* Status & Actions */}
        <div className="flex items-center gap-3 sm:gap-4 text-xs">
          
          {/* DuckDB Status */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#111418] border border-[#222831]">
            <span className={`w-1.5 h-1.5 rounded-full ${
              isDbReady ? 'bg-[#3dd68c] shadow-[0_0_8px_#3dd68c]' : initError ? 'bg-[#f2546b]' : 'bg-[#f5a524] animate-pulse'
            }`} />
            <span className={isDbReady ? 'text-[#3dd68c] font-medium' : 'text-[#a3acb9]'}>
              {isDbReady ? 'DuckDB-Wasm pronto' : initError ? 'DuckDB offline' : 'Iniciando DuckDB...'}
            </span>
          </div>

          {/* Hardware */}
          <span className="hidden md:inline-block text-[#6b7480]">
            Xeon @ 2.10GHz · 4 CPUs
          </span>

          {/* Timestamp */}
          <span className="hidden lg:inline-block text-[#6b7480]">
            Coletado 02 out 2026, 09:57
          </span>

          {/* Console SQL button */}
          <button
            onClick={scrollToConsole}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#171b21] hover:bg-[#222831] border border-[#222831] hover:border-[#2e3540] text-[#eceff3] transition-colors cursor-pointer text-xs font-medium"
          >
            <Terminal className="w-3.5 h-3.5 text-[#3dd68c]" />
            <span>Console SQL</span>
          </button>
        </div>

      </div>
    </header>
  );
}
