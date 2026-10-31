'use client';

import React, { useMemo } from 'react';
import { Trophy, AlertTriangle, ShieldCheck, Zap, Sparkles, ArrowRight } from 'lucide-react';
import { useData } from '../context/DataContext';

const langColors: Record<string, string> = {
  go: 'var(--lang-go)',
  rust: 'var(--lang-rust)',
  zig: 'var(--lang-zig)',
  java: 'var(--lang-java)',
  csharp: 'var(--lang-csharp)',
  swift: 'var(--lang-swift)',
};

const langDisplayNames: Record<string, string> = {
  rust: 'Rust',
  zig: 'Zig',
  go: 'Go',
  swift: 'Swift',
  csharp: 'C#',
  java: 'Java',
};

export default function PodiumSection() {
  const { implementations, longResults } = useData();

  // Highlight 1: Leader
  const rank1 = implementations.find(i => i.rank === 1) || implementations[0] || {
    impl_id: 'rust:hybrid:stable:libvips',
    language: 'rust',
    toolchain: 'stable 1.90',
    lib: 'libvips',
    tier: 'hybrid',
    score: 1.53,
    wins: 9,
    podiums: 16,
    coverage: 34
  };

  // Highlight 2: Rank 2
  const rank2 = implementations.find(i => i.rank === 2) || implementations[1] || {
    impl_id: 'zig:accelerated:0.15:releasefast',
    language: 'zig',
    toolchain: '0.15',
    lib: 'ReleaseFast · padrão',
    tier: 'accelerated',
    score: 1.56,
    wins: 6,
    podiums: 13,
    coverage: 24
  };

  // Highlight 3: Rank 3
  const rank3 = implementations.find(i => i.rank === 3) || implementations[2] || {
    impl_id: 'rust:accelerated:nightly:padrao',
    language: 'rust',
    toolchain: 'nightly',
    lib: 'native · padrão',
    tier: 'accelerated',
    score: 1.60,
    wins: 2,
    podiums: 19,
    coverage: 34
  };

  // Best Pure (no FFI / no C bindings)
  const bestPure = useMemo(() => {
    return implementations.find(i => 
      i.tier !== 'hybrid' && 
      !i.lib.toLowerCase().includes('cgo') && 
      !i.lib.toLowerCase().includes('libvips')
    ) || rank2;
  }, [implementations, rank2]);

  // Best by Operation
  const bestByOp = useMemo(() => {
    const calcBestForOp = (opName: string) => {
      const rows = longResults.filter(r => r.op === opName);
      if (!rows.length) return null;
      const byImpl = new Map<string, { rels: number[]; lang: string; lib: string; toolchain: string }>();
      for (const r of rows) {
        if (!byImpl.has(r.impl_id)) {
          byImpl.set(r.impl_id, { rels: [], lang: r.language, lib: r.lib, toolchain: r.toolchain });
        }
        byImpl.get(r.impl_id)!.rels.push(r.rel_time);
      }
      let bestItem = { impl_id: '', score: 999, lang: 'rust', lib: '', toolchain: '' };
      for (const [id, data] of byImpl.entries()) {
        const g = Math.exp(data.rels.reduce((acc, v) => acc + Math.log(Math.max(1.0, v)), 0) / data.rels.length);
        if (g < bestItem.score) {
          bestItem = { impl_id: id, score: Math.round(g * 100) / 100, lang: data.lang, lib: data.lib, toolchain: data.toolchain };
        }
      }
      return bestItem;
    };

    return {
      encode: calcBestForOp('encode') || { lang: 'rust', lib: 'libvips', score: 1.51 },
      decode: calcBestForOp('decode') || { lang: 'rust', lib: 'padrão', score: 1.43 },
      transcode: calcBestForOp('transcode') || { lang: 'rust', lib: 'libvips', score: 1.63 }
    };
  }, [longResults]);

  // Best per Language for logarithmic strip
  const languages = ['rust', 'zig', 'go', 'swift', 'csharp', 'java'];
  const bestByLang = useMemo(() => {
    return languages.map(lang => {
      const variants = implementations.filter(i => i.language === lang);
      variants.sort((a, b) => a.score - b.score);
      const best = variants[0] || null;
      return {
        lang,
        best,
        variants
      };
    }).filter(item => item.best !== null);
  }, [implementations]);

  // Log scale position: 1x to 8x (0% at 1x, 100% at 8x)
  const getLogPos = (score: number) => {
    const minVal = 1.0;
    const maxVal = 8.0;
    const val = Math.min(Math.max(score, minVal), maxVal);
    const pct = ((Math.log2(val) - Math.log2(minVal)) / (Math.log2(maxVal) - Math.log2(minVal))) * 100;
    return Math.max(2, Math.min(98, pct));
  };

  const formatScore = (val: number | undefined, fallback: string) => {
    return typeof val === 'number' ? val.toFixed(2).replace('.', ',') : fallback;
  };

  return (
    <section id="podium" className="mb-10 scroll-mt-28">
      
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold text-[#C9501C] dark:text-[#E0703A] uppercase tracking-wider">
              Seção 01
            </span>
            <h2 className="text-xl font-bold tracking-tight text-[var(--arena-text-primary)]">
              Pódio & Destaques de Execução
            </h2>
          </div>
          <p className="text-xs text-[var(--arena-text-secondary)] mt-1">
            Score = média geométrica do tempo relativo à melhor implementação por tarefa. 1,00× = venceu todas.
          </p>
        </div>

        <span className="text-[11px] font-mono text-[var(--arena-text-muted)]">
          Ficha oficial · 34 tarefas avaliadas
        </span>
      </div>

      {/* 5 Dynamic Executive Highlight Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
        
        {/* Card 1: Geral */}
        <div className="bg-[var(--arena-surface)] border border-[var(--arena-border)] rounded-xl p-3 flex flex-col justify-between shadow-xs">
          <div>
            <div className="flex items-center justify-between text-[11px] font-mono text-[var(--arena-text-muted)]">
              <span>LÍDER GERAL</span>
              <Trophy className="w-3.5 h-3.5 text-[#F2C14E]" />
            </div>
            <div className="mt-2 flex items-baseline gap-1.5">
              <span className="text-2xl font-bold font-mono text-[var(--arena-text-primary)]">
                {formatScore(rank1.score, '1,53')}×
              </span>
              <span className="text-[10px] text-[var(--arena-text-muted)] font-mono">relativo</span>
            </div>
          </div>
          <div className="mt-2.5 pt-2 border-t border-[var(--arena-border)]/60 text-xs">
            <div className="flex items-center gap-1.5 font-semibold text-[var(--arena-text-primary)] capitalize">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: langColors[rank1.language] }} />
              {rank1.language}
            </div>
            <p className="text-[10px] text-[var(--arena-text-secondary)] truncate font-mono mt-0.5">
              {rank1.lib} · {rank1.tier}
            </p>
          </div>
        </div>

        {/* Card 2: Sem FFI (Puro) */}
        <div className="bg-[var(--arena-surface)] border border-[var(--arena-border)] rounded-xl p-3 flex flex-col justify-between shadow-xs">
          <div>
            <div className="flex items-center justify-between text-[11px] font-mono text-[var(--arena-text-muted)]">
              <span>SEM FFI (PURO)</span>
              <ShieldCheck className="w-3.5 h-3.5 text-[#2E8B3E] dark:text-[#3DD68C]" />
            </div>
            <div className="mt-2 flex items-baseline gap-1.5">
              <span className="text-2xl font-bold font-mono text-[var(--arena-text-primary)]">
                {formatScore(bestPure.score, '1,56')}×
              </span>
              <span className="text-[10px] text-[var(--arena-text-muted)] font-mono">relativo</span>
            </div>
          </div>
          <div className="mt-2.5 pt-2 border-t border-[var(--arena-border)]/60 text-xs">
            <div className="flex items-center gap-1.5 font-semibold text-[var(--arena-text-primary)] capitalize">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: langColors[bestPure.language] }} />
              {bestPure.language}
            </div>
            <p className="text-[10px] text-[var(--arena-text-secondary)] truncate font-mono mt-0.5">
              {bestPure.toolchain} · {bestPure.lib.replace(' · padrão', '')}
            </p>
          </div>
        </div>

        {/* Card 3: Encode */}
        <div className="bg-[var(--arena-surface)] border border-[var(--arena-border)] rounded-xl p-3 flex flex-col justify-between shadow-xs">
          <div>
            <div className="flex items-center justify-between text-[11px] font-mono text-[var(--arena-text-muted)]">
              <span>MELHOR ENCODE</span>
              <Zap className="w-3.5 h-3.5 text-[#0086A3] dark:text-[#25A3B5]" />
            </div>
            <div className="mt-2 flex items-baseline gap-1.5">
              <span className="text-2xl font-bold font-mono text-[var(--arena-text-primary)]">
                {formatScore(bestByOp.encode.score, '1,51')}×
              </span>
              <span className="text-[10px] text-[var(--arena-text-muted)] font-mono">21 tarefas</span>
            </div>
          </div>
          <div className="mt-2.5 pt-2 border-t border-[var(--arena-border)]/60 text-xs">
            <div className="flex items-center gap-1.5 font-semibold text-[var(--arena-text-primary)] capitalize">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: langColors[bestByOp.encode.lang] }} />
              {bestByOp.encode.lang}
            </div>
            <p className="text-[10px] text-[var(--arena-text-secondary)] truncate font-mono mt-0.5">
              {bestByOp.encode.lib}
            </p>
          </div>
        </div>

        {/* Card 4: Decode */}
        <div className="bg-[var(--arena-surface)] border border-[var(--arena-border)] rounded-xl p-3 flex flex-col justify-between shadow-xs">
          <div>
            <div className="flex items-center justify-between text-[11px] font-mono text-[var(--arena-text-muted)]">
              <span>MELHOR DECODE</span>
              <Sparkles className="w-3.5 h-3.5 text-[#6A55D8] dark:text-[#8F7FF0]" />
            </div>
            <div className="mt-2 flex items-baseline gap-1.5">
              <span className="text-2xl font-bold font-mono text-[var(--arena-text-primary)]">
                {formatScore(bestByOp.decode.score, '1,43')}×
              </span>
              <span className="text-[10px] text-[var(--arena-text-muted)] font-mono">5 tarefas</span>
            </div>
          </div>
          <div className="mt-2.5 pt-2 border-t border-[var(--arena-border)]/60 text-xs">
            <div className="flex items-center gap-1.5 font-semibold text-[var(--arena-text-primary)] capitalize">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: langColors[bestByOp.decode.lang] }} />
              {bestByOp.decode.lang}
            </div>
            <p className="text-[10px] text-[var(--arena-text-secondary)] truncate font-mono mt-0.5">
              {bestByOp.decode.lib}
            </p>
          </div>
        </div>

        {/* Card 5: Transcode */}
        <div className="col-span-2 sm:col-span-1 bg-[var(--arena-surface)] border border-[var(--arena-border)] rounded-xl p-3 flex flex-col justify-between shadow-xs">
          <div>
            <div className="flex items-center justify-between text-[11px] font-mono text-[var(--arena-text-muted)]">
              <span>TRANSCODE</span>
              <Trophy className="w-3.5 h-3.5 text-[#9A7B00] dark:text-[#B38D1E]" />
            </div>
            <div className="mt-2 flex items-baseline gap-1.5">
              <span className="text-2xl font-bold font-mono text-[var(--arena-text-primary)]">
                {formatScore(bestByOp.transcode.score, '1,63')}×
              </span>
              <span className="text-[10px] text-[var(--arena-text-muted)] font-mono">4 tarefas</span>
            </div>
          </div>
          <div className="mt-2.5 pt-2 border-t border-[var(--arena-border)]/60 text-xs">
            <div className="flex items-center gap-1.5 font-semibold text-[var(--arena-text-primary)] capitalize">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: langColors[bestByOp.transcode.lang] }} />
              {bestByOp.transcode.lang}
            </div>
            <p className="text-[10px] text-[var(--arena-text-secondary)] truncate font-mono mt-0.5">
              {bestByOp.transcode.lib}
            </p>
          </div>
        </div>

      </div>

      {/* Main Podium Layout: Left = 3 Podium Cards, Right = Logarithmic Ruler & Purity Cost */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* 3 Podium Cards (5 columns) */}
        <div className="lg:col-span-5 grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-1 gap-3">
          
          {/* 1º Ouro */}
          <div className="relative bg-[var(--arena-surface)] border-2 border-[#F2C14E]/60 dark:border-[#F2C14E]/50 rounded-xl p-4 overflow-hidden shadow-sm flex flex-col justify-between">
            <div className="absolute top-0 left-0 right-0 h-1 bg-[#F2C14E]" />
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-[#F2C14E]/20 text-[#D9A326] dark:text-[#F2C14E] border border-[#F2C14E]/40 flex items-center justify-center text-xs font-bold font-mono">
                    1
                  </div>
                  <span className="text-xs font-semibold uppercase tracking-wider text-[var(--arena-text-primary)]">
                    Campeão Geral
                  </span>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[#9A7B00]/15 text-[#9A7B00] dark:text-[#F5A524] border border-[#9A7B00]/30 font-semibold">
                  hybrid · FFI
                </span>
              </div>

              <div className="mt-3 flex items-baseline justify-between">
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: langColors[rank1.language] }} />
                    <span className="text-base font-bold text-[var(--arena-text-primary)] capitalize">
                      {rank1.language}
                    </span>
                  </div>
                  <p className="text-xs text-[var(--arena-text-secondary)] mt-0.5">
                    {rank1.toolchain} · {rank1.lib}
                  </p>
                </div>

                <div className="text-right">
                  <span className="text-3xl font-extrabold font-mono text-[#F2C14E]">
                    {formatScore(rank1.score, '1,53')}×
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-3 pt-2.5 border-t border-[var(--arena-border)]/60 text-[11px] font-mono text-[var(--arena-text-secondary)] flex items-center justify-between">
              <span>{rank1.wins} vitórias · {rank1.podiums} pódios</span>
              <span className="text-[var(--arena-text-primary)] font-semibold">{rank1.coverage}/34 tarefas</span>
            </div>
          </div>

          {/* 2º Prata */}
          <div className="relative bg-[var(--arena-surface)] border border-[#C9D1DB]/50 dark:border-[#C9D1DB]/40 rounded-xl p-4 overflow-hidden shadow-xs flex flex-col justify-between">
            <div className="absolute top-0 left-0 right-0 h-1 bg-[#C9D1DB]/80" />
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-[#C9D1DB]/20 text-[#5E584D] dark:text-[#C9D1DB] border border-[#C9D1DB]/40 flex items-center justify-center text-xs font-bold font-mono">
                    2
                  </div>
                  <span className="text-xs font-semibold uppercase tracking-wider text-[var(--arena-text-primary)]">
                    2º Lugar
                  </span>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[var(--arena-canvas)] text-[var(--arena-text-secondary)] border border-[var(--arena-border)]">
                  {rank2.tier}
                </span>
              </div>

              <div className="mt-3 flex items-baseline justify-between">
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: langColors[rank2.language] }} />
                    <span className="text-base font-bold text-[var(--arena-text-primary)] capitalize">
                      {rank2.language}
                    </span>
                  </div>
                  <p className="text-xs text-[var(--arena-text-secondary)] mt-0.5">
                    {rank2.toolchain} · {rank2.lib}
                  </p>
                </div>

                <div className="text-right">
                  <span className="text-2xl font-bold font-mono text-[var(--arena-text-primary)]">
                    {formatScore(rank2.score, '1,56')}×
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-3 pt-2.5 border-t border-[var(--arena-border)]/60 text-[11px] font-mono text-[var(--arena-text-secondary)] flex items-center justify-between">
              <span>{rank2.wins} vitórias · {rank2.podiums} pódios</span>
              <span className="flex items-center gap-1 text-[#9A7B00] dark:text-[#F5A524] font-semibold">
                {rank2.coverage}/34 <AlertTriangle className="w-3 h-3 text-[#9A7B00] dark:text-[#F5A524]" />
              </span>
            </div>
          </div>

          {/* 3º Bronze */}
          <div className="relative bg-[var(--arena-surface)] border border-[#D08B5B]/50 dark:border-[#D08B5B]/40 rounded-xl p-4 overflow-hidden shadow-xs flex flex-col justify-between">
            <div className="absolute top-0 left-0 right-0 h-1 bg-[#D08B5B]/80" />
            <div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-[#D08B5B]/20 text-[#A65B2E] dark:text-[#D08B5B] border border-[#D08B5B]/40 flex items-center justify-center text-xs font-bold font-mono">
                    3
                  </div>
                  <span className="text-xs font-semibold uppercase tracking-wider text-[var(--arena-text-primary)]">
                    3º Lugar
                  </span>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[var(--arena-canvas)] text-[var(--arena-text-secondary)] border border-[var(--arena-border)]">
                  {rank3.tier}
                </span>
              </div>

              <div className="mt-3 flex items-baseline justify-between">
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: langColors[rank3.language] }} />
                    <span className="text-base font-bold text-[var(--arena-text-primary)] capitalize">
                      {rank3.language}
                    </span>
                  </div>
                  <p className="text-xs text-[var(--arena-text-secondary)] mt-0.5">
                    {rank3.toolchain} · {rank3.lib}
                  </p>
                </div>

                <div className="text-right">
                  <span className="text-2xl font-bold font-mono text-[var(--arena-text-primary)]">
                    {formatScore(rank3.score, '1,60')}×
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-3 pt-2.5 border-t border-[var(--arena-border)]/60 text-[11px] font-mono text-[var(--arena-text-secondary)] flex items-center justify-between">
              <span>{rank3.wins} vitórias · {rank3.podiums} pódios</span>
              <span className="text-[var(--arena-text-primary)] font-semibold">{rank3.coverage}/34 tarefas</span>
            </div>
          </div>

        </div>

        {/* Right: Logarithmic Ruler & Purity Cost (7 columns) */}
        <div className="lg:col-span-7 flex flex-col justify-between bg-[var(--arena-surface)] border border-[var(--arena-border)] rounded-xl p-5 shadow-xs">
          
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-[var(--arena-text-primary)]">
                  Melhor por Linguagem na Régua Logarítmica
                </h3>
                <p className="text-xs text-[var(--arena-text-secondary)] mt-0.5">
                  Marcador principal = melhor variante · pontos menores = outras variantes da linguagem
                </p>
              </div>

              <div className="flex items-center gap-2 text-[10px] font-mono text-[var(--arena-text-muted)]">
                <span>Escala logarítmica (1× a 8×)</span>
              </div>
            </div>

            {/* Language strips */}
            <div className="space-y-3.5 my-4">
              {bestByLang.map(({ lang, best, variants }) => {
                if (!best) return null;
                const color = langColors[lang];
                const displayName = langDisplayNames[lang] || lang;
                const bestPos = getLogPos(best.score);

                return (
                  <div key={lang} className="space-y-1">
                    <div className="flex items-center justify-between text-xs font-mono">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
                        <span className="font-semibold text-[var(--arena-text-primary)]">
                          {displayName}
                        </span>
                        <span className="text-[11px] text-[var(--arena-text-secondary)]">
                          (melhor: #{best.rank} · {best.toolchain})
                        </span>
                      </div>
                      <span className="font-bold text-[var(--arena-text-primary)]">
                        {best.score.toFixed(2).replace('.', ',')}×
                      </span>
                    </div>

                    {/* Scale line with dots */}
                    <div className="relative w-full h-5 flex items-center bg-[var(--arena-canvas)] rounded-md px-2 border border-[var(--arena-border)]/50">
                      {/* Grid tick marks at 1x, 2x, 4x, 8x */}
                      <div className="absolute left-[0%] top-0 bottom-0 w-px bg-[var(--arena-border)]" />
                      <div className="absolute left-[33.3%] top-0 bottom-0 w-px bg-[var(--arena-border)]" />
                      <div className="absolute left-[66.6%] top-0 bottom-0 w-px bg-[var(--arena-border)]" />
                      <div className="absolute left-[100%] top-0 bottom-0 w-px bg-[var(--arena-border)]" />

                      {/* Variant dots */}
                      {variants.map((v) => {
                        const isLeader = v.impl_id === best.impl_id;
                        const pos = getLogPos(v.score);
                        return (
                          <div
                            key={v.impl_id}
                            className={`absolute -translate-x-1/2 rounded-full transition-transform hover:scale-125 z-10 cursor-pointer ${
                              isLeader
                                ? 'w-3 h-3 ring-2 ring-[var(--arena-canvas)]'
                                : 'w-2 h-2 opacity-60'
                            }`}
                            style={{
                              left: `${pos}%`,
                              backgroundColor: color,
                            }}
                            title={`${v.toolchain} (${v.lib}): ${v.score.toFixed(2)}×`}
                          />
                        );
                      })}
                    </div>
                  </div>
                );
              })}

              {/* Axis labels */}
              <div className="relative w-full flex items-center justify-between text-[10px] font-mono text-[var(--arena-text-muted)] pt-1 px-1">
                <span>1,0× (Melhor)</span>
                <span>2,0×</span>
                <span>4,0×</span>
                <span>8,0×</span>
              </div>
            </div>
          </div>

          {/* Linha do Custo da Pureza (Purity Cost Line) */}
          <div className="mt-4 pt-4 border-t border-[var(--arena-border)] bg-[var(--arena-canvas)] p-3.5 rounded-lg border">
            <div className="flex items-center gap-2 mb-2">
              <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-[#C9501C]/15 dark:bg-[#E0703A]/20 text-[#C9501C] dark:text-[#E0703A] border border-[#C9501C]/30 dark:border-[#E0703A]/30">
                INSIGHT
              </span>
              <h4 className="text-xs font-bold text-[var(--arena-text-primary)]">
                O Custo da Pureza: FFI vs. Implementação Nativa
              </h4>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs mt-2.5">
              
              {/* Go Cost */}
              <div className="p-2.5 rounded-md bg-[var(--arena-surface)] border border-[var(--arena-border)] flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="font-semibold text-[#0086A3] dark:text-[#25A3B5]">Go (cgo vs PGO)</span>
                    <span className="text-[#C9501C] dark:text-[#F2546B] font-bold">+2,41× mais lento</span>
                  </div>
                  <div className="mt-1.5 flex items-center gap-2 text-xs font-mono">
                    <span className="text-[var(--arena-text-secondary)]">cgo: 1,70×</span>
                    <ArrowRight className="w-3 h-3 text-[var(--arena-text-muted)]" />
                    <span className="text-[var(--arena-text-primary)] font-bold">PGO: 4,11×</span>
                  </div>
                </div>
                <p className="text-[10px] text-[var(--arena-text-muted)] mt-2 leading-relaxed">
                  Abdicar de bibliotecas C via cgo custa mais que o dobro do tempo em compressão.
                </p>
              </div>

              {/* Rust Cost */}
              <div className="p-2.5 rounded-md bg-[var(--arena-surface)] border border-[var(--arena-border)] flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="font-semibold text-[#C9501C] dark:text-[#E0703A]">Rust (libvips vs Padrão)</span>
                    <span className="text-[#2E8B3E] dark:text-[#3DD68C] font-bold">+0,07× (+4%)</span>
                  </div>
                  <div className="mt-1.5 flex items-center gap-2 text-xs font-mono">
                    <span className="text-[var(--arena-text-secondary)]">libvips: 1,53×</span>
                    <ArrowRight className="w-3 h-3 text-[var(--arena-text-muted)]" />
                    <span className="text-[var(--arena-text-primary)] font-bold">Padrão: 1,60×</span>
                  </div>
                </div>
                <p className="text-[10px] text-[var(--arena-text-muted)] mt-2 leading-relaxed">
                  A stack 100% Rust segura entrega performance virtualmente idêntica à biblioteca C.
                </p>
              </div>

            </div>
          </div>

        </div>

      </div>

    </section>
  );
}
