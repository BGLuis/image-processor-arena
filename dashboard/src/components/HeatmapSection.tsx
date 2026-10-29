'use client';

import React, { useState, useMemo } from 'react';
import { useData } from '../context/DataContext';

const langColors: Record<string, string> = {
  go: '#2ec4e6',
  rust: '#f4743b',
  zig: '#f7c548',
  java: '#e8618c',
  csharp: '#8b7cf6',
  swift: '#a3e635',
};

export default function HeatmapSection() {
  const { longResults, implementations } = useData();
  const [showAllCols, setShowAllCols] = useState(false);
  const [tooltip, setTooltip] = useState<{
    text: string;
    sub: string;
    x: number;
    y: number;
  } | null>(null);

  // Top implementations (16 by default or 18 if expanded)
  const columns = useMemo(() => {
    const sorted = [...implementations].sort((a, b) => a.rank - b.rank);
    return showAllCols ? sorted : sorted.slice(0, 16);
  }, [implementations, showAllCols]);

  // Tasks organized by operation
  const tasksByOp = useMemo(() => {
    // Unique tasks map
    const map = new Map<number, {
      task_id: number;
      task: string;
      op: string;
      format: string;
      mode: string;
      image: string;
    }>();

    for (const r of longResults) {
      if (!map.has(r.task_id)) {
        map.set(r.task_id, {
          task_id: r.task_id,
          task: r.task,
          op: r.op,
          format: r.format,
          mode: r.mode,
          image: r.image
        });
      }
    }

    const tasks = Array.from(map.values());
    const ops = ['analyze', 'encode', 'decode', 'transcode'];

    return ops.map(op => ({
      op,
      label: op.toUpperCase(),
      tasks: tasks.filter(t => t.op.toLowerCase() === op)
    })).filter(g => g.tasks.length > 0);
  }, [longResults]);

  // Fast lookup for cells: (task_id:impl_id) -> record
  const cellMap = useMemo(() => {
    const m = new Map<string, { rel_time: number; ms: number }>();
    for (const r of longResults) {
      m.set(`${r.task_id}:${r.impl_id}`, {
        rel_time: r.rel_time,
        ms: r.codec_median_ms
      });
    }
    return m;
  }, [longResults]);

  const getHeatColorStyle = (cell?: { rel_time: number; ms: number }) => {
    if (!cell) {
      return {
        bg: 'bg-[#0d1013] border border-[#222831]',
        text: 'text-[#6b7480]',
        label: '-'
      };
    }
    const val = cell.rel_time;
    if (val <= 1.05) {
      return { bg: 'bg-[#3dd68c]', text: 'text-black font-semibold', label: '1,0×' };
    }
    if (val <= 1.5) {
      return { bg: 'bg-[#2a9f6b]', text: 'text-white', label: `${val.toFixed(1)}×` };
    }
    if (val <= 3.0) {
      return { bg: 'bg-[#1e6e4e]', text: 'text-white', label: `${val.toFixed(1)}×` };
    }
    if (val <= 10.0) {
      return { bg: 'bg-[#1d4f3a]', text: 'text-white/90', label: `${val.toFixed(0)}×` };
    }
    return { bg: 'bg-[#5c2532]', text: 'text-white', label: `${val.toFixed(0)}×` };
  };

  const handleMouseEnter = (
    e: React.MouseEvent,
    taskTitle: string,
    implTitle: string,
    cell?: { rel_time: number; ms: number }
  ) => {
    const rect = e.currentTarget.getBoundingClientRect();
    if (!cell) {
      setTooltip({
        text: `${taskTitle} · ${implTitle}`,
        sub: 'Não suportado nesta implementação',
        x: rect.left + rect.width / 2,
        y: rect.top - 8
      });
    } else {
      setTooltip({
        text: `${taskTitle} · ${implTitle}`,
        sub: `${cell.rel_time.toFixed(2).replace('.', ',')}× vs. melhor (${cell.ms.toFixed(2).replace('.', ',')} ms)`,
        x: rect.left + rect.width / 2,
        y: rect.top - 8
      });
    }
  };

  return (
    <div className="bg-[#111418] border border-[#222831] rounded-xl p-4 mb-6 shadow-sm relative">
      
      {/* Header & Legend */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-4">
        <div>
          <h2 className="text-base font-semibold text-[#eceff3]">
            Tempo relativo à melhor, por tarefa
          </h2>
          <p className="text-xs text-[#6b7480] mt-0.5">
            Cada célula = tempo de codec ÷ tempo da implementação mais rápida naquela tarefa. Colunas na ordem do ranking.
          </p>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-2 sm:gap-3 text-[11px] font-mono flex-wrap">
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded-sm bg-[#3dd68c]" />
            <span className="text-[#eceff3]">melhor</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded-sm bg-[#2a9f6b]" />
            <span className="text-[#a3acb9]">≤1,5×</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded-sm bg-[#1e6e4e]" />
            <span className="text-[#a3acb9]">≤3×</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded-sm bg-[#1d4f3a]" />
            <span className="text-[#a3acb9]">≤10×</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded-sm bg-[#5c2532]" />
            <span className="text-[#a3acb9]">&gt;10×</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded-sm bg-[#0d1013] border border-[#222831]" />
            <span className="text-[#6b7480]">sem suporte</span>
          </div>
        </div>
      </div>

      {/* Heatmap Table Matrix */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse table-fixed">
          
          {/* Header Row */}
          <thead>
            <tr className="border-b border-[#222831]">
              <th className="w-48 py-2 px-2 text-[11px] font-mono text-[#6b7480] uppercase tracking-wider">
                Tarefa
              </th>
              {columns.map(col => {
                const color = langColors[col.language] || '#a3acb9';
                const shortLib = col.lib.split(' ')[0].replace('·', '');
                return (
                  <th key={col.impl_id} className="w-14 py-2 px-0.5 text-center">
                    <div className="flex flex-col items-center">
                      <span className="text-[10px] font-mono font-bold text-[#eceff3]">
                        #{col.rank}
                      </span>
                      <div className="flex items-center gap-1 mt-0.5">
                        <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: color }} />
                        <span className="text-[10px] font-medium text-[#eceff3] capitalize truncate max-w-[40px]">
                          {col.language}
                        </span>
                      </div>
                      <span className="text-[9px] font-mono text-[#6b7480] truncate max-w-[44px]">
                        {col.tier === 'hybrid' ? 'hybrid' : shortLib}
                      </span>
                    </div>
                  </th>
                );
              })}
              {!showAllCols && implementations.length > 16 && (
                <th className="w-12 py-2 px-1 text-center">
                  <button
                    onClick={() => setShowAllCols(true)}
                    className="px-1.5 py-1 text-[10px] font-mono font-semibold text-[#3dd68c] bg-[#111418] hover:bg-[#171b21] border border-[#222831] hover:border-[#3dd68c] rounded cursor-pointer transition-colors"
                  >
                    +2 →
                  </button>
                </th>
              )}
            </tr>
          </thead>

          {/* Body with Operations */}
          <tbody>
            {tasksByOp.map(group => (
              <React.Fragment key={group.op}>
                {/* Op divider header */}
                <tr className="bg-[#0d1013]/60 border-y border-[#222831]/60">
                  <td 
                    colSpan={columns.length + (showAllCols ? 1 : 2)} 
                    className="py-1 px-2 text-[10px] font-mono font-bold text-[#a3acb9] uppercase tracking-wider"
                  >
                    {group.label}
                  </td>
                </tr>

                {/* Tasks inside Op */}
                {group.tasks.map(t => (
                  <tr key={t.task_id} className="border-b border-[#222831]/30 hover:bg-[#171b21]/40 transition-colors">
                    <td className="py-1.5 px-2 text-[11px] text-[#eceff3] truncate" title={t.task}>
                      {t.task.replace(` [${t.image}]`, ` · ${t.image.split('.')[0]}`)}
                    </td>

                    {columns.map(col => {
                      const cell = cellMap.get(`${t.task_id}:${col.impl_id}`);
                      const { bg, text, label } = getHeatColorStyle(cell);

                      return (
                        <td key={col.impl_id} className="py-1 px-0.5 text-center">
                          <div
                            onMouseEnter={(e) => handleMouseEnter(e, t.task, `${col.language} (${col.lib})`, cell)}
                            onMouseLeave={() => setTooltip(null)}
                            className={`w-full h-6 rounded-xs flex items-center justify-center text-[10px] font-mono transition-transform hover:scale-105 cursor-default ${bg} ${text}`}
                          >
                            {label}
                          </div>
                        </td>
                      );
                    })}

                    {!showAllCols && implementations.length > 16 && (
                      <td className="py-1 px-1 text-center text-[#6b7480] text-xs font-mono">
                        …
                      </td>
                    )}
                  </tr>
                ))}
              </React.Fragment>
            ))}
          </tbody>

        </table>
      </div>

      {/* Hover Tooltip */}
      {tooltip && (
        <div 
          className="fixed pointer-events-none z-50 -translate-x-1/2 -translate-y-full px-2.5 py-1.5 rounded bg-[#171b21] border border-[#2e3540] text-xs shadow-xl text-center"
          style={{ left: `${tooltip.x}px`, top: `${tooltip.y}px` }}
        >
          <div className="font-semibold text-[#eceff3]">{tooltip.text}</div>
          <div className="text-[11px] font-mono text-[#3dd68c] mt-0.5">{tooltip.sub}</div>
        </div>
      )}

    </div>
  );
}
