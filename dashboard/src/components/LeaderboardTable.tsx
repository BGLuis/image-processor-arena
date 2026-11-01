'use client';

import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Check, AlertTriangle, Info, ShieldCheck } from 'lucide-react';
import { useData } from '../context/DataContext';
import type { ImplementationSummary } from '../types';
import { langColor, langLabel } from '../lib/languages';

export default function LeaderboardTable() {
  const { 
    implementations, 
    languages,
    totalTasks,
    totalImplementations,
    metadata,
    filters, 
    duelImplA, 
    duelImplB, 
    toggleDuelSelection 
  } = useData();

  // Collapsed groups state
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});

  const toggleGroup = (lang: string) => {
    setCollapsedGroups(prev => ({ ...prev, [lang]: !prev[lang] }));
  };

  const filteredImpls = implementations;

  const grouped = languages.map(lang => {
    const items = filteredImpls.filter(i => i.language === lang);
    return {
      lang,
      items,
      count: items.length,
      best: items[0] || null
    };
  }).filter(g => g.count > 0);

  const env = metadata?.environment;
  const slotLabel = (implId: string) => {
    const impl = implementations.find(i => i.impl_id === implId);
    return impl ? `${langLabel(impl.language)} ${impl.lib}` : '-';
  };

  const getRankBadge = (rank: number) => {
    if (rank === 1) {
      return (
        <div className="w-5 h-5 rounded-full bg-[#F2C14E]/20 border border-[#F2C14E]/40 flex items-center justify-center text-[#D9A326] dark:text-[#F2C14E] text-[11px] font-bold font-mono">
          1
        </div>
      );
    }
    if (rank === 2) {
      return (
        <div className="w-5 h-5 rounded-full bg-[#C9D1DB]/20 border border-[#C9D1DB]/40 flex items-center justify-center text-[#5E584D] dark:text-[#C9D1DB] text-[11px] font-bold font-mono">
          2
        </div>
      );
    }
    if (rank === 3) {
      return (
        <div className="w-5 h-5 rounded-full bg-[#D08B5B]/20 border border-[#D08B5B]/40 flex items-center justify-center text-[#A65B2E] dark:text-[#D08B5B] text-[11px] font-bold font-mono">
          3
        </div>
      );
    }
    return (
      <div className="w-5 h-5 rounded-full bg-[var(--arena-canvas)] border border-[var(--arena-border)] flex items-center justify-center text-[var(--arena-text-secondary)] text-[11px] font-mono">
        {rank}
      </div>
    );
  };

  const getLogPos = (v: number) => {
    const minVal = 1.0;
    const maxVal = 8.0;
    const clamped = Math.max(minVal, Math.min(maxVal, v));
    return ((Math.log2(clamped) - Math.log2(minVal)) / (Math.log2(maxVal) - Math.log2(minVal))) * 100;
  };

  const renderRow = (item: ImplementationSummary) => {
    const isSelectedA = item.impl_id === duelImplA;
    const isSelectedB = item.impl_id === duelImplB;
    const isSelected = isSelectedA || isSelectedB;
    const color = langColor(item.language);

    const p25Val = item.p25 ?? item.score;
    const p75Val = item.p75 ?? item.score;
    const pos25 = getLogPos(p25Val);
    const pos75 = getLogPos(p75Val);
    const posScore = getLogPos(item.score);

    return (
      <tr 
        key={item.impl_id}
        onClick={() => toggleDuelSelection(item.impl_id)}
        className={`group border-b border-[var(--arena-border)]/50 hover:bg-[var(--arena-raised)]/60 transition-colors cursor-pointer text-xs ${
          isSelected ? 'bg-[var(--arena-raised)]/80' : ''
        }`}
      >
        {/* Duelo Slot Badge (A or B) with direct selection buttons */}
        <td className="py-2.5 pl-3 pr-2 w-14">
          <div className="flex items-center justify-center">
            {isSelectedA ? (
              <span className="w-5 h-5 rounded-full bg-[#C9501C] dark:bg-[#E0703A] text-white text-[11px] font-mono font-bold flex items-center justify-center shadow-xs" title="Slot A do Duelo (clique para alternar)">
                A
              </span>
            ) : isSelectedB ? (
              <span className="w-5 h-5 rounded-full bg-[#0086A3] dark:bg-[#25A3B5] text-white text-[11px] font-mono font-bold flex items-center justify-center shadow-xs" title="Slot B do Duelo (clique para alternar)">
                B
              </span>
            ) : (
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleDuelSelection(item.impl_id, 'A');
                  }}
                  className="w-4 h-4 rounded text-[9px] font-mono font-bold bg-[#C9501C]/20 hover:bg-[#C9501C] text-[#C9501C] hover:text-white transition-colors flex items-center justify-center cursor-pointer"
                  title="Definir como Implementação A"
                >
                  A
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleDuelSelection(item.impl_id, 'B');
                  }}
                  className="w-4 h-4 rounded text-[9px] font-mono font-bold bg-[#0086A3]/20 hover:bg-[#0086A3] text-[#0086A3] hover:text-white transition-colors flex items-center justify-center cursor-pointer"
                  title="Definir como Implementação B"
                >
                  B
                </button>
              </div>
            )}
          </div>
        </td>

        {/* Rank */}
        <td className="py-2.5 px-2 w-10">
          {getRankBadge(item.rank)}
        </td>

        {/* Implementação */}
        <td className="py-2.5 px-3 min-w-[220px]">
          <div className="flex items-center gap-2">
            <span 
              className="w-2 h-2 rounded-full shrink-0" 
              style={{ backgroundColor: color }} 
            />
            <span className="font-semibold text-[var(--arena-text-primary)]">
              {langLabel(item.language)}
            </span>
            <span className="text-[var(--arena-text-secondary)] text-[11px] truncate">
              {item.toolchain} · {item.lib}
            </span>
          </div>
        </td>

        {/* Tier */}
        <td className="py-2.5 px-3 w-28">
          {item.tier === 'hybrid' ? (
            <span className="inline-block text-[10px] font-mono px-2 py-0.5 rounded-full bg-[#9A7B00]/15 text-[#9A7B00] dark:text-[#F5A524] border border-[#9A7B00]/30 font-semibold">
              hybrid · FFI
            </span>
          ) : item.tier === 'accelerated' ? (
            <span className="inline-block text-[10px] font-mono px-2 py-0.5 rounded-full bg-[var(--arena-canvas)] border border-[var(--arena-border)] text-[var(--arena-text-secondary)]">
              accelerated
            </span>
          ) : (
            <span className="inline-block text-[10px] font-mono px-2 py-0.5 rounded-full bg-[var(--arena-canvas)] border border-[var(--arena-border)] text-[var(--arena-text-muted)]">
              portable
            </span>
          )}
        </td>

        {/* Score & Logarithmic Span [p25, p75] Bar */}
        <td className="py-2.5 px-3 min-w-[220px]">
          <div className="flex items-center gap-3">
            <span className="w-12 font-mono font-bold text-[var(--arena-text-primary)] shrink-0">
              {item.score.toFixed(2).replace('.', ',')}×
            </span>
            <div 
              className="relative flex-1 h-5 bg-[var(--arena-canvas)] rounded-md border border-[var(--arena-border)]/60 flex items-center overflow-hidden"
              title={`Score: ${item.score.toFixed(2)}× · Intervalo p25-p75: [${p25Val.toFixed(2)}×, ${p75Val.toFixed(2)}×]`}
            >
              {/* Reference scale tick marks at 1x, 2x, 4x, 8x */}
              <div className="absolute left-[0%] top-0 bottom-0 w-px bg-[var(--arena-border)]" />
              <div className="absolute left-[33.3%] top-0 bottom-0 w-px bg-[var(--arena-border)]/40" />
              <div className="absolute left-[66.7%] top-0 bottom-0 w-px bg-[var(--arena-border)]/40" />
              <div className="absolute left-[100%] top-0 bottom-0 w-px bg-[var(--arena-border)]" />

              {/* Shaded span [p25, p75] */}
              <div 
                className="absolute top-1 bottom-1 rounded-xs transition-all duration-300"
                style={{ 
                  left: `${pos25}%`,
                  width: `${Math.max(4, pos75 - pos25)}%`,
                  backgroundColor: color,
                  opacity: 0.3
                }} 
              />

              {/* Whisker line from p25 to p75 */}
              <div 
                className="absolute top-1/2 -translate-y-1/2 h-px transition-all duration-300"
                style={{
                  left: `${pos25}%`,
                  width: `${Math.max(2, pos75 - pos25)}%`,
                  backgroundColor: color,
                }}
              >
                <div className="absolute left-0 top-[-2px] w-px h-1.5" style={{ backgroundColor: color }} />
                <div className="absolute right-0 top-[-2px] w-px h-1.5" style={{ backgroundColor: color }} />
              </div>

              {/* Median Score Marker */}
              <div 
                className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 w-1.5 h-3 rounded-xs shadow-xs z-10 transition-all duration-300"
                style={{ 
                  left: `${posScore}%`,
                  backgroundColor: color
                }} 
              />
            </div>
          </div>
        </td>

        {/* Vitórias */}
        <td className="py-2.5 px-3 text-right font-mono text-[var(--arena-text-secondary)] w-20">
          {item.wins > 0 ? (
            <span className="text-[var(--arena-text-primary)] font-semibold">{item.wins}</span>
          ) : (
            <span className="text-[var(--arena-text-muted)]">0</span>
          )}
        </td>

        {/* Pódios */}
        <td className="py-2.5 px-3 text-right font-mono text-[var(--arena-text-secondary)] w-20">
          {item.podiums}
        </td>

        {/* Cobertura */}
        <td className="py-2.5 pl-3 pr-4 text-right font-mono text-[var(--arena-text-secondary)] w-24">
          {item.coverage === totalTasks ? (
            <span>{totalTasks}/{totalTasks}</span>
          ) : (
            <span className="text-[#9A7B00] dark:text-[#F5A524] flex items-center justify-end gap-1 font-semibold">
              {item.coverage}/{totalTasks} <AlertTriangle className="w-3 h-3 text-[#9A7B00] dark:text-[#F5A524]" />
            </span>
          )}
        </td>
      </tr>
    );
  };

  return (
    <section id="ranking" className="mb-10 scroll-mt-28">
      
      {/* Verified Real Data Banner */}
      <div className="mb-3 px-3.5 py-2.5 rounded-lg bg-[var(--arena-surface)] border border-[#2E8B3E]/30 dark:border-[#3DD68C]/30 flex items-center justify-between text-xs text-[var(--arena-text-secondary)]">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-[#2E8B3E] dark:text-[#3DD68C] shrink-0" />
          <span>
            <strong className="text-[var(--arena-text-primary)]">Dados 100% Reais e Auditados</strong>
            {env?.cpu && <> · Medições em {env.cpu} ({env.cpu_count} CPUs lógicas, {env.platform})</>}
            {' '}· Clique em qualquer linha para alimentar os slots <strong>A</strong> e <strong>B</strong> do Duelo.
          </span>
        </div>
        <span className="hidden sm:inline font-mono text-[11px] text-[var(--arena-text-muted)] shrink-0">
          Slots ativos: A ({slotLabel(duelImplA)}) · B ({slotLabel(duelImplB)})
        </span>
      </div>

      <div className="bg-[var(--arena-surface)] border border-[var(--arena-border)] rounded-xl p-4 shadow-sm">
        
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-[#C9501C] dark:text-[#E0703A] uppercase tracking-wider">
                Seção 04
              </span>
              <h2 className="text-xl font-bold tracking-tight text-[var(--arena-text-primary)]">
                Ranking de Implementações
              </h2>
            </div>
            <p className="text-xs text-[var(--arena-text-secondary)] mt-1">
              {filters.groupByLanguage ? 'Agrupado por linguagem com ordenação de variantes' : 'Ordenação plana por score global'}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="px-2.5 py-1 text-xs font-mono rounded-full bg-[var(--arena-canvas)] border border-[var(--arena-border)] text-[var(--arena-text-secondary)]">
              {filteredImpls.length} de {totalImplementations} implementações
            </span>
          </div>
        </div>

        {/* Table Container */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            
            {/* Column Headers */}
            <thead>
              <tr className="border-b border-[var(--arena-border)] text-[11px] font-mono text-[var(--arena-text-muted)] uppercase tracking-wider">
                <th className="py-2 pl-3 pr-2 w-14 text-center">Duelo</th>
                <th className="py-2 px-2 w-10">#</th>
                <th className="py-2 px-3">Implementação</th>
                <th className="py-2 px-3 w-28">Tier</th>
                <th className="py-2 px-3 min-w-[220px]">Score [p25, p75] log (1× a 8×) ↑</th>
                <th className="py-2 px-3 text-right w-20">Vitórias</th>
                <th className="py-2 px-3 text-right w-20">Pódios</th>
                <th className="py-2 pl-3 pr-4 text-right w-24">Cobertura</th>
              </tr>
            </thead>

            <tbody>
              {filters.groupByLanguage ? (
                grouped.map(group => {
                  const isCollapsed = !!collapsedGroups[group.lang];
                  const color = langColor(group.lang);
                  const displayName = langLabel(group.lang);

                  return (
                    <React.Fragment key={group.lang}>
                      {/* Collapsible Group Header Row */}
                      <tr 
                        onClick={() => toggleGroup(group.lang)}
                        className="bg-[var(--arena-canvas)]/90 hover:bg-[var(--arena-raised)] border-y border-[var(--arena-border)] cursor-pointer transition-colors text-xs"
                      >
                        <td colSpan={8} className="py-2 px-3">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              {isCollapsed ? (
                                <ChevronRight className="w-4 h-4 text-[var(--arena-text-muted)]" />
                              ) : (
                                <ChevronDown className="w-4 h-4 text-[var(--arena-text-muted)]" />
                              )}
                              <span 
                                className="w-2 h-2 rounded-full" 
                                style={{ backgroundColor: color }} 
                              />
                              <span className="font-bold text-[var(--arena-text-primary)]">
                                {displayName}
                              </span>
                              <span className="text-[var(--arena-text-muted)] text-[11px] font-mono">
                                ({group.count} {group.count === 1 ? 'variante' : 'variantes'})
                              </span>
                            </div>

                            {group.best && (
                              <span className="text-[11px] font-mono text-[var(--arena-text-secondary)]">
                                melhor #{group.best.rank} · {group.best.score.toFixed(2).replace('.', ',')}×
                              </span>
                            )}
                          </div>
                        </td>
                      </tr>

                      {/* Group Rows */}
                      {!isCollapsed && group.items.map(item => renderRow(item))}
                    </React.Fragment>
                  );
                })
              ) : (
                filteredImpls.map(item => renderRow(item))
              )}
            </tbody>

          </table>
        </div>

      </div>

    </section>
  );
}
