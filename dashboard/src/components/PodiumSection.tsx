'use client';

import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { useData } from '../context/DataContext';

const langColors: Record<string, string> = {
  go: '#2ec4e6',
  rust: '#f4743b',
  zig: '#f7c548',
  java: '#e8618c',
  csharp: '#8b7cf6',
  swift: '#a3e635',
};

export default function PodiumSection() {
  const { implementations } = useData();

  const rank1 = implementations.find(i => i.rank === 1) || {
    language: 'rust',
    toolchain: 'stable 1.90',
    lib: 'libvips',
    tier: 'hybrid',
    score: 1.53,
    wins: 9,
    podiums: 16,
    coverage: 34
  };

  const rank2 = implementations.find(i => i.rank === 2) || {
    language: 'zig',
    toolchain: '0.15',
    lib: 'ReleaseFast · padrão',
    tier: 'accelerated',
    score: 1.56,
    wins: 6,
    podiums: 13,
    coverage: 24
  };

  const rank3 = implementations.find(i => i.rank === 3) || {
    language: 'rust',
    toolchain: 'nightly',
    lib: 'native · padrão',
    tier: 'accelerated',
    score: 1.60,
    wins: 2,
    podiums: 19,
    coverage: 34
  };

  const formatScore = (val: number | undefined, fallback: string) => {
    return typeof val === 'number' ? val.toFixed(2).replace('.', ',') : fallback;
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      
      {/* Card 1: Rodada Summary */}
      <div className="bg-[#111418] border border-[#222831] rounded-xl p-4 flex flex-col justify-between">
        <div>
          <span className="text-xs text-[#a3acb9] font-medium tracking-wide">
            Rodada · 02 out 2026
          </span>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-4xl font-bold tracking-tight text-[#eceff3]">
              18
            </span>
            <span className="text-sm text-[#a3acb9]">
              implementações
            </span>
          </div>
          <div className="mt-2 text-[11px] font-mono text-[#6b7480] flex items-center gap-1.5 flex-wrap">
            <span>6 linguagens</span>
            <span>·</span>
            <span>34 tarefas</span>
            <span>·</span>
            <span>3 tiers</span>
          </div>
        </div>

        <p className="mt-4 text-[11px] text-[#6b7480] leading-relaxed border-t border-[#222831] pt-3">
          Score = média geométrica do tempo relativo à melhor implementação de cada tarefa. 1,00× = venceu todas.
        </p>
      </div>

      {/* Card 2: 1º Lugar (Ouro) */}
      <div className="bg-[#111418] border border-[#816b33]/60 rounded-xl p-4 relative overflow-hidden flex flex-col justify-between shadow-[0_0_20px_rgba(242,193,78,0.06)]">
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-[#f2c14e] to-transparent opacity-80" />
        
        <div>
          {/* Header Badge & Tier */}
          <div className="flex items-center justify-between">
            <div className="w-6 h-6 rounded-full bg-[#312c20] border border-[#816b33] flex items-center justify-center text-[#f2c14e] text-xs font-bold font-mono">
              1
            </div>
            <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#31281a] border border-[#835d1e] text-[#f5a524]">
              hybrid · FFI
            </span>
          </div>

          {/* Identity */}
          <div className="mt-3">
            <div className="flex items-center gap-1.5">
              <span 
                className="w-2.5 h-2.5 rounded-full" 
                style={{ backgroundColor: langColors[rank1.language] || '#f4743b' }} 
              />
              <span className="text-sm font-semibold text-[#eceff3] capitalize">
                {rank1.language}
              </span>
            </div>
            <p className="text-xs text-[#a3acb9] mt-0.5 truncate">
              {rank1.toolchain} · {rank1.lib}
            </p>
          </div>

          {/* Big Score */}
          <div className="mt-4 flex items-baseline gap-1.5">
            <span className="text-3xl font-bold font-mono text-[#f2c14e]">
              {formatScore(rank1.score, '1,53')}×
            </span>
            <span className="text-xs text-[#a3acb9]">
              vs. melhor
            </span>
          </div>
        </div>

        {/* Stats */}
        <div className="mt-4 pt-3 border-t border-[#222831] text-[11px] font-mono text-[#a3acb9]">
          {rank1.wins} vitórias · {rank1.podiums} pódios · {rank1.coverage}/34 tarefas
        </div>
      </div>

      {/* Card 3: 2º Lugar (Prata) */}
      <div className="bg-[#111418] border border-[#6d737a]/60 rounded-xl p-4 relative overflow-hidden flex flex-col justify-between shadow-[0_0_20px_rgba(201,209,219,0.04)]">
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-[#c9d1db] to-transparent opacity-60" />

        <div>
          {/* Header Badge & Tier */}
          <div className="flex items-center justify-between">
            <div className="w-6 h-6 rounded-full bg-[#2b2e33] border border-[#6d737a] flex items-center justify-center text-[#c9d1db] text-xs font-bold font-mono">
              2
            </div>
            <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#171b21] border border-[#2e3540] text-[#a3acb9]">
              {rank2.tier}
            </span>
          </div>

          {/* Identity */}
          <div className="mt-3">
            <div className="flex items-center gap-1.5">
              <span 
                className="w-2.5 h-2.5 rounded-full" 
                style={{ backgroundColor: langColors[rank2.language] || '#f7c548' }} 
              />
              <span className="text-sm font-semibold text-[#eceff3] capitalize">
                {rank2.language}
              </span>
            </div>
            <p className="text-xs text-[#a3acb9] mt-0.5 truncate">
              {rank2.toolchain} · {rank2.lib}
            </p>
          </div>

          {/* Big Score */}
          <div className="mt-4 flex items-baseline gap-1.5">
            <span className="text-3xl font-bold font-mono text-[#c9d1db]">
              {formatScore(rank2.score, '1,56')}×
            </span>
            <span className="text-xs text-[#a3acb9]">
              vs. melhor
            </span>
          </div>
        </div>

        {/* Stats */}
        <div className="mt-4 pt-3 border-t border-[#222831] text-[11px] font-mono text-[#a3acb9] flex items-center justify-between">
          <span>{rank2.wins} vitórias · {rank2.podiums} pódios</span>
          <span className="flex items-center gap-1 text-[#f5a524]">
            {rank2.coverage}/34 <AlertTriangle className="w-3 h-3 text-[#f5a524]" />
          </span>
        </div>
      </div>

      {/* Card 4: 3º Lugar (Bronze) */}
      <div className="bg-[#111418] border border-[#71503a]/60 rounded-xl p-4 relative overflow-hidden flex flex-col justify-between shadow-[0_0_20px_rgba(208,139,91,0.04)]">
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-[#d08b5b] to-transparent opacity-60" />

        <div>
          {/* Header Badge & Tier */}
          <div className="flex items-center justify-between">
            <div className="w-6 h-6 rounded-full bg-[#2c2521] border border-[#71503a] flex items-center justify-center text-[#d08b5b] text-xs font-bold font-mono">
              3
            </div>
            <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#171b21] border border-[#2e3540] text-[#a3acb9]">
              {rank3.tier}
            </span>
          </div>

          {/* Identity */}
          <div className="mt-3">
            <div className="flex items-center gap-1.5">
              <span 
                className="w-2.5 h-2.5 rounded-full" 
                style={{ backgroundColor: langColors[rank3.language] || '#f4743b' }} 
              />
              <span className="text-sm font-semibold text-[#eceff3] capitalize">
                {rank3.language}
              </span>
            </div>
            <p className="text-xs text-[#a3acb9] mt-0.5 truncate">
              {rank3.toolchain} · {rank3.lib}
            </p>
          </div>

          {/* Big Score */}
          <div className="mt-4 flex items-baseline gap-1.5">
            <span className="text-3xl font-bold font-mono text-[#d08b5b]">
              {formatScore(rank3.score, '1,60')}×
            </span>
            <span className="text-xs text-[#a3acb9]">
              vs. melhor
            </span>
          </div>
        </div>

        {/* Stats */}
        <div className="mt-4 pt-3 border-t border-[#222831] text-[11px] font-mono text-[#a3acb9]">
          {rank3.wins} vitórias · {rank3.podiums} pódios · {rank3.coverage}/34 tarefas
        </div>
      </div>

    </div>
  );
}
