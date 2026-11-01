'use client';

import React, { useState, useMemo } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { useData } from '../context/DataContext';

const langColors: Record<string, string> = {
  go: 'var(--lang-go)',
  rust: 'var(--lang-rust)',
};

export default function HeatmapSection() {
  const { longResults, implementations } = useData();
  const [showValues, setShowValues] = useState(true);
  const [tooltip, setTooltip] = useState<{
    text: string;
    sub: string;
    x: number;
    y: number;
  } | null>(null);

  // Implementations sorted by rank (Rust and Go)
  const columns = useMemo(() => {
    return [...implementations].sort((a, b) => a.rank - b.rank);
  }, [implementations]);

  // Tasks organized by operation
  const tasksByOp = useMemo(() => {
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

  // 5-step Indigo Ramp style mapping
  const getIndigoStyle = (cell?: { rel_time: number; ms: number }) => {
    if (!cell) {
      return {
        className: 'bg-[var(--arena-canvas)] border border-[var(--arena-border)] text-[var(--arena-text-muted)] hatch-pattern',
        label: '-'
      };
    }
    const val = cell.rel_time;
    if (val <= 1.05) {
      // Step 1: Best
      return { 
        className: 'bg-[#4338CA] dark:bg-[#6366F1] text-white font-bold shadow-xs', 
        label: '1,0×' 
      };
    }
    if (val <= 1.5) {
      // Step 2: <= 1.5x
      return { 
        className: 'bg-[#4F46E5] dark:bg-[#4F46E5] text-white font-medium', 
        label: `${val.toFixed(1)}×` 
      };
    }
    if (val <= 3.0) {
      // Step 3: <= 3x
      return { 
        className: 'bg-[#6366F1] dark:bg-[#4338CA] text-white font-medium', 
        label: `${val.toFixed(1)}×` 
      };
    }
    if (val <= 10.0) {
      // Step 4: <= 10x
      return { 
        className: 'bg-[#818CF8] dark:bg-[#312E81] text-slate-900 dark:text-white/90', 
        label: `${val.toFixed(0)}×` 
      };
    }
    // Step 5: > 10x
    return { 
      className: 'bg-[#C7D2FE] dark:bg-[#1E1B4B] text-indigo-950 dark:text-indigo-200/90', 
      label: `${val.toFixed(0)}×` 
    };
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
        sub: 'Sem suporte nesta implementação',
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
    <section id="matrix" className="mb-10 scroll-mt-28">
      
      <div className="bg-[var(--arena-surface)] border border-[var(--arena-border)] rounded-xl p-4 sm:p-5 shadow-sm relative">
        
        {/* Header, Legend & Toggle */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-5">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-[#C9501C] dark:text-[#E0703A] uppercase tracking-wider">
                Seção 05
              </span>
              <h2 className="text-xl font-bold tracking-tight text-[var(--arena-text-primary)]">
                Matriz Tarefa × Implementação
              </h2>
            </div>
            <p className="text-xs text-[var(--arena-text-secondary)] mt-1">
              Tempo de codec relativo à melhor implementação por tarefa. Células escuras indicam maior velocidade.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            
            {/* Indigo Ramp Legend */}
            <div className="flex items-center gap-2 text-[11px] font-mono flex-wrap">
              <div className="flex items-center gap-1.5">
                <span className="w-3.5 h-3.5 rounded-xs bg-[#4338CA] dark:bg-[#6366F1]" />
                <span className="text-[var(--arena-text-primary)] font-bold">1,0×</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3.5 h-3.5 rounded-xs bg-[#4F46E5] dark:bg-[#4F46E5]" />
                <span className="text-[var(--arena-text-secondary)]">≤1,5×</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3.5 h-3.5 rounded-xs bg-[#6366F1] dark:bg-[#4338CA]" />
                <span className="text-[var(--arena-text-secondary)]">≤3×</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3.5 h-3.5 rounded-xs bg-[#818CF8] dark:bg-[#312E81]" />
                <span className="text-[var(--arena-text-secondary)]">≤10×</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3.5 h-3.5 rounded-xs bg-[#C7D2FE] dark:bg-[#1E1B4B]" />
                <span className="text-[var(--arena-text-secondary)]">&gt;10×</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3.5 h-3.5 rounded-xs bg-[var(--arena-canvas)] border border-[var(--arena-border)] hatch-pattern" />
                <span className="text-[var(--arena-text-muted)]">sem suporte</span>
              </div>
            </div>

            {/* Toggle Values */}
            <button
              onClick={() => setShowValues(prev => !prev)}
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono rounded-md bg-[var(--arena-canvas)] hover:bg-[var(--arena-raised)] border border-[var(--arena-border)] text-[var(--arena-text-secondary)] hover:text-[var(--arena-text-primary)] transition-colors cursor-pointer"
            >
              {showValues ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
              <span>{showValues ? 'Ocultar valores' : 'Exibir valores'}</span>
            </button>

          </div>
        </div>

        {/* Heatmap Table */}
        <div className="overflow-x-auto border border-[var(--arena-border)] rounded-lg bg-[var(--arena-canvas)]">
          <table className="w-full text-left border-collapse table-fixed min-w-[640px]">
            
            {/* Table Header */}
            <thead>
              <tr className="border-b border-[var(--arena-border)] bg-[var(--arena-surface)]">
                <th className="w-64 sm:w-80 py-2.5 px-3 text-[11px] font-mono text-[var(--arena-text-muted)] uppercase tracking-wider sticky left-0 z-20 bg-[var(--arena-surface)] border-r border-[var(--arena-border)]">
                  Tarefa
                </th>
                {columns.map(col => {
                  const color = langColors[col.language] || 'var(--lang-rust)';
                  const langName = col.language === 'rust' ? 'Rust' : 'Go';
                  return (
                    <th key={col.impl_id} className="w-28 sm:w-36 py-2 px-2 text-center">
                      <div className="flex flex-col items-center">
                        <span className="text-[10px] font-mono font-bold text-[var(--arena-text-primary)]">
                          #{col.rank}
                        </span>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
                          <span className="text-xs font-bold text-[var(--arena-text-primary)]">
                            {langName}
                          </span>
                        </div>
                        <span className="text-[9px] font-mono text-[var(--arena-text-muted)] truncate max-w-[140px]">
                          {col.toolchain} · {col.lib}
                        </span>
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>

            {/* Table Body */}
            <tbody>
              {tasksByOp.map(group => (
                <React.Fragment key={group.op}>
                  {/* Operation Divider Row */}
                  <tr className="bg-[var(--arena-surface)] border-y border-[var(--arena-border)]/80">
                    <td 
                      colSpan={columns.length + 1} 
                      className="py-1 px-3 text-[10px] font-mono font-bold text-[var(--arena-text-secondary)] uppercase tracking-wider sticky left-0 bg-[var(--arena-surface)]"
                    >
                      {group.label} ({group.tasks.length} tarefas)
                    </td>
                  </tr>

                  {/* Tasks inside Op */}
                  {group.tasks.map(t => (
                    <tr key={t.task_id} className="border-b border-[var(--arena-border)]/30 hover:bg-[var(--arena-raised)]/30 transition-colors">
                      {/* Task Name Column (sticky left) */}
                      <td className="py-1.5 px-3 text-[11px] font-medium text-[var(--arena-text-primary)] truncate sticky left-0 z-10 bg-[var(--arena-canvas)] border-r border-[var(--arena-border)]/60" title={t.task}>
                        {t.task.replace(` [${t.image}]`, ` · ${t.image.split('.')[0]}`)}
                      </td>

                      {/* Implementation Cells */}
                      {columns.map(col => {
                        const cell = cellMap.get(`${t.task_id}:${col.impl_id}`);
                        const { className, label } = getIndigoStyle(cell);

                        return (
                          <td key={col.impl_id} className="py-1 px-1.5 text-center">
                            <div
                              onMouseEnter={(e) => handleMouseEnter(e, t.task, `${col.language === 'rust' ? 'Rust' : 'Go'} (${col.lib})`, cell)}
                              onMouseLeave={() => setTooltip(null)}
                              className={`w-full h-7 rounded-sm flex items-center justify-center text-[10px] font-mono transition-transform hover:scale-105 cursor-default ${className}`}
                            >
                              {showValues ? label : ''}
                            </div>
                          </td>
                        );
                      })}
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
            className="fixed pointer-events-none z-50 -translate-x-1/2 -translate-y-full px-2.5 py-1.5 rounded-lg bg-[var(--arena-surface)] border border-[var(--arena-border-strong)] text-xs shadow-xl text-center"
            style={{ left: `${tooltip.x}px`, top: `${tooltip.y}px` }}
          >
            <div className="font-bold text-[var(--arena-text-primary)]">{tooltip.text}</div>
            <div className="text-[11px] font-mono text-[#4338CA] dark:text-[#6366F1] mt-0.5 font-semibold">{tooltip.sub}</div>
          </div>
        )}

      </div>

    </section>
  );
}
