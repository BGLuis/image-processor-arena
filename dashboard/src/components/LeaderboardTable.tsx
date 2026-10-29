'use client';

import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Check, AlertTriangle } from 'lucide-react';
import { useData } from '../context/DataContext';
import type { ImplementationSummary } from '../types';

const langColors: Record<string, string> = {
  go: '#2ec4e6',
  rust: '#f4743b',
  zig: '#f7c548',
  java: '#e8618c',
  csharp: '#8b7cf6',
  swift: '#a3e635',
};

const langDisplayNames: Record<string, string> = {
  rust: 'Rust',
  zig: 'Zig',
  go: 'Go',
  swift: 'Swift',
  csharp: 'C#',
  java: 'Java',
};

export default function LeaderboardTable() {
  const { 
    implementations, 
    filters, 
    duelImplA, 
    duelImplB, 
    toggleDuelSelection 
  } = useData();

  // Collapsed groups state (default: Swift, C#, Java collapsed)
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({
    swift: true,
    csharp: true,
    java: true,
  });

  const toggleGroup = (lang: string) => {
    setCollapsedGroups(prev => ({ ...prev, [lang]: !prev[lang] }));
  };

  // Filter implementations according to identity filters
  const filteredImpls = implementations.filter(item => {
    if (filters.language !== 'all' && item.language !== filters.language) return false;
    if (filters.tier !== 'all' && item.tier !== filters.tier) return false;
    if (filters.toolchain !== 'all' && item.toolchain !== filters.toolchain) return false;
    if (filters.lib !== 'all' && item.lib !== filters.lib) return false;
    return true;
  });

  // Group by language order: Rust, Zig, Go, Swift, C#, Java
  const langOrder = ['rust', 'zig', 'go', 'swift', 'csharp', 'java'];
  const grouped = langOrder.map(lang => {
    const items = filteredImpls.filter(i => i.language === lang);
    return {
      lang,
      items,
      count: items.length,
      best: items[0] || null
    };
  }).filter(g => g.count > 0);

  const getRankBadge = (rank: number) => {
    if (rank === 1) {
      return (
        <div className="w-5 h-5 rounded-full bg-[#312c20] border border-[#816b33] flex items-center justify-center text-[#f2c14e] text-[11px] font-bold font-mono">
          1
        </div>
      );
    }
    if (rank === 2) {
      return (
        <div className="w-5 h-5 rounded-full bg-[#2b2e33] border border-[#6d737a] flex items-center justify-center text-[#c9d1db] text-[11px] font-bold font-mono">
          2
        </div>
      );
    }
    if (rank === 3) {
      return (
        <div className="w-5 h-5 rounded-full bg-[#2c2521] border border-[#71503a] flex items-center justify-center text-[#d08b5b] text-[11px] font-bold font-mono">
          3
        </div>
      );
    }
    return (
      <div className="w-5 h-5 rounded-full bg-[#171b21] border border-[#222831] flex items-center justify-center text-[#a3acb9] text-[11px] font-mono">
        {rank}
      </div>
    );
  };

  const renderRow = (item: ImplementationSummary) => {
    const isSelectedA = item.impl_id === duelImplA;
    const isSelectedB = item.impl_id === duelImplB;
    const isSelected = isSelectedA || isSelectedB;
    const color = langColors[item.language] || '#a3acb9';

    // Calculate score bar width (from 1x up to 8x scale)
    const barWidthPercent = Math.min(100, Math.max(8, ((item.score - 1.0) / 7.0) * 100));

    return (
      <tr 
        key={item.impl_id}
        onClick={() => toggleDuelSelection(item.impl_id)}
        className={`group border-b border-[#222831]/50 hover:bg-[#171b21]/70 transition-colors cursor-pointer text-xs ${
          isSelected ? 'bg-[#171b21]/90' : ''
        }`}
      >
        {/* Checkbox */}
        <td className="py-2.5 pl-3 pr-2 w-8">
          <div className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
            isSelected 
              ? isSelectedA ? 'bg-[#f4743b] border-[#f4743b] text-white' : 'bg-[#2ec4e6] border-[#2ec4e6] text-black'
              : 'border-[#2e3540] bg-[#0d1013] group-hover:border-[#6b7480]'
          }`}>
            {isSelected && <Check className="w-3 h-3 stroke-[3]" />}
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
            <span className="font-semibold text-[#eceff3] capitalize">
              {item.language}
            </span>
            <span className="text-[#a3acb9] text-[11px] truncate">
              {item.toolchain} · {item.lib}
            </span>
          </div>
        </td>

        {/* Tier */}
        <td className="py-2.5 px-3 w-28">
          {item.tier === 'hybrid' ? (
            <span className="inline-block text-[10px] font-mono px-2 py-0.5 rounded-full bg-[#31281a] border border-[#835d1e] text-[#f5a524]">
              hybrid · FFI
            </span>
          ) : item.tier === 'accelerated' ? (
            <span className="inline-block text-[10px] font-mono px-2 py-0.5 rounded-full bg-[#171b21] border border-[#2e3540] text-[#a3acb9]">
              accelerated
            </span>
          ) : (
            <span className="inline-block text-[10px] font-mono px-2 py-0.5 rounded-full bg-[#0d1013] border border-[#222831] text-[#6b7480]">
              portable
            </span>
          )}
        </td>

        {/* Score & Bar */}
        <td className="py-2.5 px-3 min-w-[180px]">
          <div className="flex items-center gap-3">
            <span className="w-12 font-mono font-bold text-[#eceff3]">
              {item.score.toFixed(2).replace('.', ',')}×
            </span>
            <div className="flex-1 h-1.5 bg-[#0d1013] rounded-full overflow-hidden">
              <div 
                className="h-full rounded-full transition-all duration-300"
                style={{ 
                  width: `${barWidthPercent}%`,
                  backgroundColor: color
                }} 
              />
            </div>
          </div>
        </td>

        {/* Vitórias */}
        <td className="py-2.5 px-3 text-right font-mono text-[#a3acb9] w-20">
          {item.wins > 0 ? (
            <span className="text-[#eceff3] font-semibold">{item.wins}</span>
          ) : (
            <span className="text-[#6b7480]">0</span>
          )}
        </td>

        {/* Pódios */}
        <td className="py-2.5 px-3 text-right font-mono text-[#a3acb9] w-20">
          {item.podiums}
        </td>

        {/* Cobertura */}
        <td className="py-2.5 pl-3 pr-4 text-right font-mono text-[#a3acb9] w-24">
          {item.coverage === 34 ? (
            <span className="text-[#a3acb9]">34/34</span>
          ) : (
            <span className="text-[#f5a524] flex items-center justify-end gap-1 font-semibold">
              {item.coverage}/34 <AlertTriangle className="w-3 h-3 text-[#f5a524]" />
            </span>
          )}
        </td>
      </tr>
    );
  };

  return (
    <div className="bg-[#111418] border border-[#222831] rounded-xl p-4 mb-6 shadow-sm">
      
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-base font-semibold text-[#eceff3]">
            Ranking de implementações
          </h2>
          <p className="text-xs text-[#6b7480] mt-0.5">
            {filters.groupByLanguage ? 'Agrupado por linguagem' : 'Ordenação plana por score'} · selecione 2 linhas para o duelo
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 text-xs font-mono rounded-full bg-[#1d4f3a]/40 border border-[#2a9f6b]/50 text-[#3dd68c]">
            2 selecionadas
          </span>
        </div>
      </div>

      {/* Table Container */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          
          {/* Column Headers */}
          <thead>
            <tr className="border-b border-[#222831] text-[11px] font-mono text-[#6b7480] uppercase tracking-wider">
              <th className="py-2 pl-3 pr-2 w-8" />
              <th className="py-2 px-2 w-10">#</th>
              <th className="py-2 px-3">Implementação</th>
              <th className="py-2 px-3 w-28">Tier</th>
              <th className="py-2 px-3 min-w-[180px]">Score (média geom.) ↑</th>
              <th className="py-2 px-3 text-right w-20">Vitórias</th>
              <th className="py-2 px-3 text-right w-20">Pódios</th>
              <th className="py-2 pl-3 pr-4 text-right w-24">Cobertura</th>
            </tr>
          </thead>

          <tbody>
            {filters.groupByLanguage ? (
              grouped.map(group => {
                const isCollapsed = !!collapsedGroups[group.lang];
                const color = langColors[group.lang] || '#a3acb9';
                const displayName = langDisplayNames[group.lang] || group.lang;

                return (
                  <React.Fragment key={group.lang}>
                    {/* Collapsible Group Header Row */}
                    <tr 
                      onClick={() => toggleGroup(group.lang)}
                      className="bg-[#0d1013]/90 hover:bg-[#171b21] border-y border-[#222831] cursor-pointer transition-colors text-xs"
                    >
                      <td colSpan={8} className="py-2 px-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            {isCollapsed ? (
                              <ChevronRight className="w-4 h-4 text-[#6b7480]" />
                            ) : (
                              <ChevronDown className="w-4 h-4 text-[#6b7480]" />
                            )}
                            <span 
                              className="w-2 h-2 rounded-full" 
                              style={{ backgroundColor: color }} 
                            />
                            <span className="font-semibold text-[#eceff3]">
                              {displayName}
                            </span>
                            <span className="text-[#6b7480] text-[11px]">
                              {group.count} {group.count === 1 ? 'implementação' : 'implementações'}
                            </span>
                          </div>

                          {group.best && (
                            <span className="text-[11px] font-mono text-[#a3acb9]">
                              melhor #{group.best.rank} · {group.best.score.toFixed(2).replace('.', ',')}×
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>

                    {/* Group Rows (if not collapsed) */}
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
  );
}
