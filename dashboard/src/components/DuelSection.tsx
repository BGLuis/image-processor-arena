'use client';

import React, { useState, useMemo } from 'react';
import { Swords, ArrowLeftRight, HelpCircle, Check, Award } from 'lucide-react';
import { useData } from '../context/DataContext';

const langColors: Record<string, string> = {
  go: 'var(--lang-go)',
  rust: 'var(--lang-rust)',
};

export default function DuelSection() {
  const { 
    longResults, 
    implementations, 
    duelImplA, 
    duelImplB, 
    setDuelImplA, 
    setDuelImplB 
  } = useData();

  const [metricTab, setMetricTab] = useState<'speedup' | 'latency' | 'throughput' | 'bytes'>('speedup');

  const implA = implementations.find(i => i.impl_id === duelImplA) || implementations[0];
  const implB = implementations.find(i => i.impl_id === duelImplB) || implementations[1];

  const colorA = langColors[implA?.language] || '#E0703A';
  const colorB = langColors[implB?.language] || '#25A3B5';

  // Compare results between Impl A and Impl B per task with exact p25-p75 overlap tie criterion
  const duelRows = useMemo(() => {
    const tasksMap = new Map<number, {
      task: string;
      op: string;
      image: string;
      format: string;
      rowA?: any;
      rowB?: any;
    }>();

    for (const r of longResults) {
      if (r.impl_id === duelImplA || r.impl_id === duelImplB) {
        if (!tasksMap.has(r.task_id)) {
          tasksMap.set(r.task_id, {
            task: r.task,
            op: r.op,
            image: r.image,
            format: r.format,
          });
        }
        const item = tasksMap.get(r.task_id)!;
        if (r.impl_id === duelImplA) item.rowA = r;
        if (r.impl_id === duelImplB) item.rowB = r;
      }
    }

    const compared: Array<{
      taskId: number;
      task: string;
      op: string;
      image: string;
      format: string;
      ratio: number; // medianB / medianA (>1 = A is faster, <1 = B is faster)
      speedupDisplay: string;
      winner: 'A' | 'B' | 'TIE';
      isTie: boolean;
      medianA: number;
      medianB: number;
      p25A: number;
      p75A: number;
      p25B: number;
      p75B: number;
      bytesA: number;
      bytesB: number;
      mp: number;
    }> = [];

    for (const [taskId, data] of tasksMap.entries()) {
      if (!data.rowA || !data.rowB) continue;

      const tA = data.rowA.codec_median_ms || 1.0;
      const tB = data.rowB.codec_median_ms || 1.0;
      const p25A = data.rowA.p25 ?? tA * 0.95;
      const p75A = data.rowA.p75 ?? tA * 1.05;
      const p25B = data.rowB.p25 ?? tB * 0.95;
      const p75B = data.rowB.p75 ?? tB * 1.05;

      // Mathematical overlap tie criterion: max(p25_A, p25_B) <= min(p75_A, p75_B)
      const isTie = Math.max(p25A, p25B) <= Math.min(p75A, p75B);

      const ratio = tA > 0 ? tB / tA : 1.0;
      let winner: 'A' | 'B' | 'TIE' = 'TIE';
      let factor = 1.0;

      if (isTie) {
        winner = 'TIE';
        factor = ratio >= 1.0 ? ratio : 1.0 / ratio;
      } else if (tA < tB) {
        winner = 'A';
        factor = ratio;
      } else {
        winner = 'B';
        factor = 1.0 / ratio;
      }

      compared.push({
        taskId,
        task: data.task.replace(` [${data.image}]`, ` · ${data.image?.split('.')[0] || ''}`),
        op: data.op,
        image: data.image,
        format: data.format,
        ratio,
        speedupDisplay: `${(factor || 1.0).toFixed(2).replace('.', ',')}×`,
        winner,
        isTie,
        medianA: tA,
        medianB: tB,
        p25A,
        p75A,
        p25B,
        p75B,
        bytesA: data.rowA.bytes || 0,
        bytesB: data.rowB.bytes || 0,
        mp: data.rowA.mp || 0.26,
      });
    }

    // Sort order: A fastest on top down to B fastest
    compared.sort((a, b) => b.ratio - a.ratio);
    return compared;
  }, [longResults, duelImplA, duelImplB]);

  // Overall summary & per-operation stats for divergent lollipop
  const summary = useMemo(() => {
    let winsA = 0;
    let winsB = 0;
    let ties = 0;
    const logRatios: number[] = [];
    const opMap: Record<string, number[]> = {
      analyze: [],
      encode: [],
      decode: [],
      transcode: [],
    };

    for (const row of duelRows) {
      if (row.winner === 'A') winsA++;
      else if (row.winner === 'B') winsB++;
      else ties++;

      logRatios.push(Math.log(Math.max(0.01, row.ratio)));

      if (opMap[row.op]) {
        opMap[row.op].push(row.ratio);
      }
    }

    const geomean = logRatios.length 
      ? Math.exp(logRatios.reduce((a, b) => a + b, 0) / logRatios.length)
      : 1.0;

    const opList = ['analyze', 'encode', 'decode', 'transcode'].map(op => {
      const ratios = opMap[op] || [];
      if (!ratios.length) return { op, geomean: 1.0, isAFaster: true, factor: 1.0, count: 0 };
      const g = Math.exp(ratios.reduce((a, b) => a + Math.log(Math.max(0.01, b)), 0) / ratios.length);
      const isAFaster = g >= 1.0;
      return {
        op,
        geomean: g,
        isAFaster,
        factor: isAFaster ? g : 1.0 / g,
        count: ratios.length
      };
    });

    return {
      winsA,
      winsB,
      ties,
      geomean,
      isAFaster: geomean >= 1.0,
      factor: geomean >= 1.0 ? geomean : 1.0 / geomean,
      opList
    };
  }, [duelRows]);

  const swapAB = () => {
    const temp = duelImplA;
    setDuelImplA(duelImplB);
    setDuelImplB(temp);
  };

  return (
    <section id="duel" className="mb-10 scroll-mt-28">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold text-[#C9501C] dark:text-[#E0703A] uppercase tracking-wider">
              Seção 02
            </span>
            <h2 className="text-xl font-bold tracking-tight text-[var(--arena-text-primary)]">
              Duelo Par-a-Par (A × B)
            </h2>
          </div>
          <p className="text-xs text-[var(--arena-text-secondary)] mt-1">
            Comparação direta com critério estatístico de empate por sobreposição dos intervalos interquartis [p25, p75].
          </p>
        </div>

        {/* Metric Selector Tabs */}
        <div className="flex items-center p-0.5 bg-[var(--arena-surface)] border border-[var(--arena-border)] rounded-lg text-xs font-mono">
          <button
            onClick={() => setMetricTab('speedup')}
            className={`px-2.5 py-1 rounded cursor-pointer transition-colors ${
              metricTab === 'speedup' ? 'bg-[var(--arena-canvas)] text-[var(--arena-text-primary)] font-bold shadow-xs' : 'text-[var(--arena-text-secondary)] hover:text-[var(--arena-text-primary)]'
            }`}
          >
            Speedup
          </button>
          <button
            onClick={() => setMetricTab('latency')}
            className={`px-2.5 py-1 rounded cursor-pointer transition-colors ${
              metricTab === 'latency' ? 'bg-[var(--arena-canvas)] text-[var(--arena-text-primary)] font-bold shadow-xs' : 'text-[var(--arena-text-secondary)] hover:text-[var(--arena-text-primary)]'
            }`}
          >
            Latência (ms)
          </button>
          <button
            onClick={() => setMetricTab('throughput')}
            className={`px-2.5 py-1 rounded cursor-pointer transition-colors ${
              metricTab === 'throughput' ? 'bg-[var(--arena-canvas)] text-[var(--arena-text-primary)] font-bold shadow-xs' : 'text-[var(--arena-text-secondary)] hover:text-[var(--arena-text-primary)]'
            }`}
          >
            Throughput (MP/s)
          </button>
          <button
            onClick={() => setMetricTab('bytes')}
            className={`px-2.5 py-1 rounded cursor-pointer transition-colors ${
              metricTab === 'bytes' ? 'bg-[var(--arena-canvas)] text-[var(--arena-text-primary)] font-bold shadow-xs' : 'text-[var(--arena-text-secondary)] hover:text-[var(--arena-text-primary)]'
            }`}
          >
            Tamanho
          </button>
        </div>
      </div>

      {/* Main Duel Grid */}
      <div className="bg-[var(--arena-surface)] border border-[var(--arena-border)] rounded-xl p-4 sm:p-5 shadow-sm">
        
        {/* Implementation Selectors */}
        <div className="grid grid-cols-1 sm:grid-cols-11 gap-3 items-center mb-6">
          
          {/* Selector A */}
          <div className="sm:col-span-5 p-3 rounded-lg bg-[var(--arena-canvas)] border border-[var(--arena-border)]">
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-[#C9501C] dark:bg-[#E0703A] text-white text-[11px] font-mono font-bold flex items-center justify-center">
                  A
                </span>
                <span className="text-xs font-bold text-[var(--arena-text-primary)]">
                  Implementação A
                </span>
              </div>
              <span className="text-[10px] font-mono text-[var(--arena-text-muted)]">
                Score #{implA?.rank} · {implA?.score.toFixed(2)}×
              </span>
            </div>
            <select
              value={duelImplA}
              onChange={(e) => setDuelImplA(e.target.value)}
              className="w-full text-xs bg-[var(--arena-surface)] border border-[var(--arena-border)] rounded px-2.5 py-1.5 text-[var(--arena-text-primary)] cursor-pointer focus:outline-none font-mono"
            >
              {implementations.map(impl => (
                <option key={impl.impl_id} value={impl.impl_id}>
                  {impl.language.toUpperCase()} ({impl.tier} · {impl.toolchain} · {impl.lib})
                </option>
              ))}
            </select>
          </div>

          {/* Swap Button */}
          <div className="sm:col-span-1 flex justify-center">
            <button
              onClick={swapAB}
              className="p-2 rounded-full bg-[var(--arena-canvas)] hover:bg-[var(--arena-raised)] border border-[var(--arena-border)] text-[var(--arena-text-secondary)] hover:text-[var(--arena-text-primary)] transition-all cursor-pointer shadow-xs"
              title="Inverter A e B"
            >
              <ArrowLeftRight className="w-4 h-4" />
            </button>
          </div>

          {/* Selector B */}
          <div className="sm:col-span-5 p-3 rounded-lg bg-[var(--arena-canvas)] border border-[var(--arena-border)]">
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-[#0086A3] dark:bg-[#25A3B5] text-white text-[11px] font-mono font-bold flex items-center justify-center">
                  B
                </span>
                <span className="text-xs font-bold text-[var(--arena-text-primary)]">
                  Implementação B
                </span>
              </div>
              <span className="text-[10px] font-mono text-[var(--arena-text-muted)]">
                Score #{implB?.rank} · {implB?.score.toFixed(2)}×
              </span>
            </div>
            <select
              value={duelImplB}
              onChange={(e) => setDuelImplB(e.target.value)}
              className="w-full text-xs bg-[var(--arena-surface)] border border-[var(--arena-border)] rounded px-2.5 py-1.5 text-[var(--arena-text-primary)] cursor-pointer focus:outline-none font-mono"
            >
              {implementations.map(impl => (
                <option key={impl.impl_id} value={impl.impl_id}>
                  {impl.language.toUpperCase()} ({impl.tier} · {impl.toolchain} · {impl.lib})
                </option>
              ))}
            </select>
          </div>

        </div>

        {/* Duel Scoreboard & Divergent Lollipop Section */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 pb-6 mb-6 border-b border-[var(--arena-border)]">
          
          {/* Placar do Duelo (5 cols) */}
          <div className="lg:col-span-5 bg-[var(--arena-canvas)] border border-[var(--arena-border)] rounded-xl p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between text-xs font-bold font-mono mb-2">
                <span className="text-[#C9501C] dark:text-[#E0703A]">A: {summary.winsA} vitórias</span>
                <span className="text-[var(--arena-text-secondary)]">{summary.ties} {summary.ties === 1 ? 'empate' : 'empates'}</span>
                <span className="text-[#0086A3] dark:text-[#25A3B5]">B: {summary.winsB} vitórias</span>
              </div>

              {/* Progress Split Bar */}
              <div className="h-3.5 w-full bg-[var(--arena-surface)] rounded-full overflow-hidden flex border border-[var(--arena-border)]">
                <div 
                  className="h-full bg-[#C9501C] dark:bg-[#E0703A] transition-all" 
                  style={{ width: `${(summary.winsA / (duelRows.length || 1)) * 100}%` }}
                  title={`A venceu ${summary.winsA} tarefas`} 
                />
                <div 
                  className="h-full bg-[var(--arena-border-strong)] transition-all" 
                  style={{ width: `${(summary.ties / (duelRows.length || 1)) * 100}%` }}
                  title={`${summary.ties} empates estatísticos`} 
                />
                <div 
                  className="h-full bg-[#0086A3] dark:bg-[#25A3B5] transition-all" 
                  style={{ width: `${(summary.winsB / (duelRows.length || 1)) * 100}%` }}
                  title={`B venceu ${summary.winsB} tarefas`} 
                />
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-[var(--arena-border)]/60 flex items-center justify-between">
              <div>
                <span className="text-[10px] font-mono text-[var(--arena-text-muted)] uppercase">
                  Média Geométrica Geral
                </span>
                <div className="text-xl font-bold font-mono text-[var(--arena-text-primary)]">
                  {summary.factor.toFixed(2).replace('.', ',')}×
                </div>
              </div>
              <span className={`text-xs font-mono font-semibold px-2.5 py-1 rounded-full border ${
                summary.isAFaster
                  ? 'bg-[#C9501C]/15 dark:bg-[#E0703A]/20 text-[#C9501C] dark:text-[#E0703A] border-[#C9501C]/30 dark:border-[#E0703A]/30'
                  : 'bg-[#0086A3]/15 dark:bg-[#25A3B5]/20 text-[#0086A3] dark:text-[#25A3B5] border-[#0086A3]/30 dark:border-[#25A3B5]/30'
              }`}>
                {summary.isAFaster ? 'A é mais rápido no geral' : 'B é mais rápido no geral'}
              </span>
            </div>
          </div>

          {/* Divergent Lollipop Chart by Operation (7 cols) */}
          <div className="lg:col-span-7 bg-[var(--arena-canvas)] border border-[var(--arena-border)] rounded-xl p-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-[var(--arena-text-primary)]">
                  Agrupamento Divergente por Operação (Lollipop)
                </span>
                <span className="text-[10px] font-mono text-[var(--arena-text-muted)]">
                  Centro = 1,0× (Empate)
                </span>
              </div>

              {/* Axis indicator */}
              <div className="relative w-full flex items-center justify-between text-[10px] font-mono text-[var(--arena-text-muted)] mb-3 pb-1 border-b border-[var(--arena-border)]">
                <span className="text-[#0086A3] dark:text-[#25A3B5]">← B mais rápido</span>
                <span className="font-bold text-[var(--arena-text-primary)]">1,0×</span>
                <span className="text-[#C9501C] dark:text-[#E0703A]">A mais rápido →</span>
              </div>

              {/* Lollipops */}
              <div className="space-y-3">
                {summary.opList.map(item => {
                  // Map factor to width %: 1.0x = 0%, 5.0x = 44%
                  const widthPct = Math.min(44, Math.max(4, (Math.log2(Math.max(1.0, item.factor)) / Math.log2(5.0)) * 44));

                  return (
                    <div key={item.op} className="relative flex items-center h-6 text-xs font-mono">
                      {/* Left stem for B */}
                      <div className="flex-1 flex justify-end items-center h-full pr-1 relative">
                        {!item.isAFaster && (
                          <div className="flex items-center">
                            <span className="mr-2 text-[10px] font-bold text-[#0086A3] dark:text-[#25A3B5]">
                              {item.factor.toFixed(2).replace('.', ',')}×
                            </span>
                            <div 
                              className="h-0.5 bg-[#0086A3] dark:bg-[#25A3B5] transition-all"
                              style={{ width: `${widthPct * 2.5}px` }}
                            />
                            <div className="w-2.5 h-2.5 rounded-full bg-[#0086A3] dark:bg-[#25A3B5] shrink-0 shadow-xs" />
                          </div>
                        )}
                      </div>

                      {/* Center Axis Line & Label */}
                      <div className="w-24 shrink-0 flex items-center justify-center relative">
                        <div className="absolute top-0 bottom-0 left-1/2 w-px bg-[var(--arena-border)]" />
                        <span className="relative z-10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider rounded bg-[var(--arena-surface)] border border-[var(--arena-border)] text-[var(--arena-text-secondary)]">
                          {item.op}
                        </span>
                      </div>

                      {/* Right stem for A */}
                      <div className="flex-1 flex justify-start items-center h-full pl-1 relative">
                        {item.isAFaster && (
                          <div className="flex items-center">
                            <div className="w-2.5 h-2.5 rounded-full bg-[#C9501C] dark:bg-[#E0703A] shrink-0 shadow-xs" />
                            <div 
                              className="h-0.5 bg-[#C9501C] dark:bg-[#E0703A] transition-all"
                              style={{ width: `${widthPct * 2.5}px` }}
                            />
                            <span className="ml-2 text-[10px] font-bold text-[#C9501C] dark:text-[#E0703A]">
                              {item.factor.toFixed(2).replace('.', ',')}×
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <p className="mt-3 text-[10px] text-[var(--arena-text-muted)] font-mono text-center">
              Comprimento da haste proporcional à razão da média geométrica dos tempos de codec na operação.
            </p>
          </div>

        </div>

        {/* SVG Dumbbell Chart Task by Task */}
        <div>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
            <div>
              <h3 className="text-sm font-bold text-[var(--arena-text-primary)]">
                Gráfico Dumbbell com Whiskers [p25, p75] por Tarefa
              </h3>
              <p className="text-xs text-[var(--arena-text-secondary)]">
                Linha conecta as medianas · hastes representam o intervalo p25 a p75 · destaque sombreado indica empate estatístico por sobreposição.
              </p>
            </div>

            {/* Legend */}
            <div className="flex items-center gap-3 text-[11px] font-mono">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-[#C9501C] dark:bg-[#E0703A]" />
                <span className="text-[var(--arena-text-secondary)]">A (Rust)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-[#0086A3] dark:bg-[#25A3B5]" />
                <span className="text-[var(--arena-text-secondary)]">B (Go)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-2 rounded-xs bg-[#9A7B00]/25 border border-[#9A7B00]/40" />
                <span className="text-[var(--arena-text-secondary)]">Sobreposição (Empate)</span>
              </div>
            </div>
          </div>

          {/* Dumbbell Rows Container */}
          <div className="space-y-1.5 max-h-[620px] overflow-y-auto pr-1">
            {duelRows.map(row => {
              // Calculate domain for this task row
              const minTime = Math.min(row.p25A, row.p25B);
              const maxTime = Math.max(row.p75A, row.p75B);
              const padMin = Math.max(0.1, minTime * 0.75);
              const padMax = maxTime * 1.25;
              const logMin = Math.log10(padMin);
              const logMax = Math.log10(padMax);
              const span = Math.max(0.01, logMax - logMin);

              const timeToPct = (t: number) => {
                const logT = Math.log10(Math.max(0.01, t));
                return Math.max(2, Math.min(98, ((logT - logMin) / span) * 100));
              };

              const xA = timeToPct(row.medianA);
              const xB = timeToPct(row.medianB);
              const x25A = timeToPct(row.p25A);
              const x75A = timeToPct(row.p75A);
              const x25B = timeToPct(row.p25B);
              const x75B = timeToPct(row.p75B);

              const overlapLeft = timeToPct(Math.max(row.p25A, row.p25B));
              const overlapRight = timeToPct(Math.min(row.p75A, row.p75B));

              // Value display based on active metric tab
              let valDisplayA = `${row.medianA.toFixed(1)} ms`;
              let valDisplayB = `${row.medianB.toFixed(1)} ms`;
              if (metricTab === 'throughput') {
                const mpA = row.medianA > 0 ? (row.mp / (row.medianA / 1000)).toFixed(1) : '0';
                const mpB = row.medianB > 0 ? (row.mp / (row.medianB / 1000)).toFixed(1) : '0';
                valDisplayA = `${mpA} MP/s`;
                valDisplayB = `${mpB} MP/s`;
              } else if (metricTab === 'bytes') {
                valDisplayA = `${(row.bytesA / 1024).toFixed(1)} KB`;
                valDisplayB = `${(row.bytesB / 1024).toFixed(1)} KB`;
              }

              return (
                <div 
                  key={row.taskId} 
                  className={`group relative flex items-center h-10 px-3 rounded-lg border transition-colors ${
                    row.isTie
                      ? 'bg-[var(--arena-canvas)] border-[#9A7B00]/40 dark:border-[#B38D1E]/40'
                      : 'bg-[var(--arena-canvas)] border-[var(--arena-border)] hover:border-[var(--arena-border-strong)]'
                  }`}
                >
                  {/* Task Name & Format */}
                  <div className="w-56 sm:w-64 shrink-0 flex items-center gap-2 truncate pr-2">
                    <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-[var(--arena-surface)] border border-[var(--arena-border)] text-[var(--arena-text-muted)]">
                      {row.op}
                    </span>
                    <span className="text-xs font-medium text-[var(--arena-text-primary)] truncate" title={row.task}>
                      {row.task}
                    </span>
                  </div>

                  {/* Dumbbell visualization with aligned whiskers and round circles */}
                  <div className="flex-1 h-8 flex items-center relative px-2">
                    {/* Tie overlap shaded region */}
                    {row.isTie && overlapLeft <= overlapRight && (
                      <div 
                        className="absolute top-1 bottom-1 rounded bg-[#9A7B00]/20 border border-[#9A7B00]/40 pointer-events-none z-0"
                        style={{
                          left: `${overlapLeft}%`,
                          width: `${Math.max(1, overlapRight - overlapLeft)}%`
                        }}
                        title={`Sobreposição de empate: [${Math.max(row.p25A, row.p25B).toFixed(1)} ms, ${Math.min(row.p75A, row.p75B).toFixed(1)} ms]`}
                      />
                    )}

                    {/* Whisker A (Top line at 26%) */}
                    <div 
                      className="absolute top-[26%] h-px border-t border-dashed border-[#C9501C] dark:border-[#E0703A] pointer-events-none"
                      style={{ 
                        left: `${Math.min(x25A, x75A)}%`, 
                        width: `${Math.max(0.5, Math.abs(x75A - x25A))}%` 
                      }}
                    >
                      <div className="absolute left-0 top-[-3px] w-px h-2 bg-[#C9501C] dark:bg-[#E0703A]" />
                      <div className="absolute right-0 top-[-3px] w-px h-2 bg-[#C9501C] dark:bg-[#E0703A]" />
                    </div>

                    {/* Whisker B (Bottom line at 74%) */}
                    <div 
                      className="absolute top-[74%] h-px border-t border-dashed border-[#0086A3] dark:border-[#25A3B5] pointer-events-none"
                      style={{ 
                        left: `${Math.min(x25B, x75B)}%`, 
                        width: `${Math.max(0.5, Math.abs(x75B - x25B))}%` 
                      }}
                    >
                      <div className="absolute left-0 top-[-3px] w-px h-2 bg-[#0086A3] dark:bg-[#25A3B5]" />
                      <div className="absolute right-0 top-[-3px] w-px h-2 bg-[#0086A3] dark:bg-[#25A3B5]" />
                    </div>

                    {/* Diagonal connecting dumbbell bar */}
                    <svg className="absolute inset-0 w-full h-full pointer-events-none overflow-visible">
                      <line 
                        x1={`${xA}%`} 
                        y1="26%" 
                        x2={`${xB}%`} 
                        y2="74%" 
                        stroke="var(--arena-border-strong)" 
                        strokeWidth="1.5" 
                      />
                    </svg>

                    {/* Circle Point A (median at 26%) */}
                    <div 
                      className="absolute top-[26%] -translate-x-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-[#C9501C] dark:bg-[#E0703A] ring-2 ring-[var(--arena-canvas)] z-10 shadow-xs cursor-pointer transition-transform hover:scale-125"
                      style={{ left: `${xA}%` }}
                      title={`A: ${valDisplayA} (p25: ${row.p25A.toFixed(1)} ms, p75: ${row.p75A.toFixed(1)} ms)`}
                    />

                    {/* Circle Point B (median at 74%) */}
                    <div 
                      className="absolute top-[74%] -translate-x-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-[#0086A3] dark:bg-[#25A3B5] ring-2 ring-[var(--arena-canvas)] z-10 shadow-xs cursor-pointer transition-transform hover:scale-125"
                      style={{ left: `${xB}%` }}
                      title={`B: ${valDisplayB} (p25: ${row.p25B.toFixed(1)} ms, p75: ${row.p75B.toFixed(1)} ms)`}
                    />
                  </div>

                  {/* Values readout & Speedup Badge */}
                  <div className="w-48 sm:w-56 shrink-0 flex items-center justify-end gap-2 pl-2 text-xs font-mono">
                    <span className="hidden sm:inline text-[10px] text-[var(--arena-text-muted)]">
                      {valDisplayA} vs {valDisplayB}
                    </span>

                    {/* Result Badge */}
                    {row.isTie ? (
                      <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-[#9A7B00]/15 text-[#9A7B00] dark:text-[#F5A524] border border-[#9A7B00]/30">
                        Empate ({row.speedupDisplay})
                      </span>
                    ) : row.winner === 'A' ? (
                      <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-[#C9501C]/15 dark:bg-[#E0703A]/20 text-[#C9501C] dark:text-[#E0703A] border border-[#C9501C]/30 dark:border-[#E0703A]/30">
                        A +{row.speedupDisplay}
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-[#0086A3]/15 dark:bg-[#25A3B5]/20 text-[#0086A3] dark:text-[#25A3B5] border border-[#0086A3]/30 dark:border-[#25A3B5]/30">
                        B +{row.speedupDisplay}
                      </span>
                    )}
                  </div>

                </div>
              );
            })}
          </div>
        </div>

      </div>

    </section>
  );
}
