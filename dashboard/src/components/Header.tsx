'use client';

import React from 'react';
import { Trophy, Cpu, Database, ShieldCheck, Flame } from 'lucide-react';
import { useData } from '../context/DataContext';

export default function Header() {
  const { metadata, isDbReady, initError } = useData();

  return (
    <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          
          {/* Logo e Título */}
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-br from-amber-500/20 to-orange-500/20 border border-amber-500/30 text-amber-400">
              <Trophy className="w-7 h-7" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
                  Image Processor Arena
                </h1>
                <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-cyan-950 border border-cyan-800 text-cyan-400">
                  Go Puro × Rust Puro
                </span>
              </div>
              <p className="text-xs sm:text-sm text-slate-400">
                Pódio analítico interativo e benchmark rigoroso (0% CGO / 0% FFI)
              </p>
            </div>
          </div>

          {/* Badges de Status e Hardware */}
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {/* DuckDB Status */}
            <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border font-mono ${
              isDbReady 
                ? 'bg-emerald-950/50 border-emerald-800/80 text-emerald-400'
                : initError
                ? 'bg-rose-950/50 border-rose-800/80 text-rose-400'
                : 'bg-amber-950/50 border-amber-800/80 text-amber-400'
            }`}>
              <Database className="w-3.5 h-3.5" />
              <span>
                {isDbReady ? 'DuckDB-Wasm OLAP Ativo' : initError ? 'DuckDB Erro (Modo Fallback)' : 'Carregando DuckDB...'}
              </span>
            </div>

            {/* Hardware */}
            {metadata?.environment?.cpu && (
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300">
                <Cpu className="w-3.5 h-3.5 text-slate-400" />
                <span className="truncate max-w-[180px] sm:max-w-none">
                  {metadata.environment.cpu} ({metadata.environment.cpu_count} CPUs)
                </span>
              </div>
            )}

            {/* Pureza */}
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-cyan-400 font-mono">
              <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
              <span>100% Puro</span>
            </div>
          </div>

        </div>
      </div>
    </header>
  );
}
