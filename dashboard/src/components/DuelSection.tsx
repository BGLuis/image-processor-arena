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

export default function DuelSection() {
  const { 
    longResults, 
    implementations, 
    equalQuality, 
    duelImplA, 
    duelImplB, 
    setDuelImplA, 
    setDuelImplB 
  } = useData();

  const [metricTab, setMetricTab] = useState<'speedup' | 'throughput' | 'latency' | 'bytes'>('speedup');

  const implA = implementations.find(i => i.impl_id === duelImplA) || implementations[4] || implementations[0];
  const implB = implementations.find(i => i.impl_id === duelImplB) || implementations[9] || implementations[1];

  const colorA = langColors[implA?.language] || '#f4743b';
  const colorB = langColors[implB?.language] || '#2ec4e6';

  // Compare results between Impl A and Impl B per task
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
      ratio: number; // timeB / timeA (>1 = A is faster, <1 = B is faster)
      speedupDisplay: string;
      faster: 'A' | 'B' | 'TIE';
      timeA: number;
      timeB: number;
      bytesA: number;
      bytesB: number;
    }> = [];

    for (const [taskId, data] of tasksMap.entries()) {
      if (!data.rowA || !data.rowB) continue;
      const tA = data.rowA.codec_median_ms || 1.0;
      const tB = data.rowB.codec_median_ms || 1.0;
      const ratio = tA > 0 ? tB / tA : 1.0;

      let faster: 'A' | 'B' | 'TIE' = 'TIE';
      if (ratio > 1.03) faster = 'A';
      else if (ratio < 0.97) faster = 'B';

      const factor = faster === 'A' ? ratio : 1.0 / ratio;

      compared.push({
        taskId,
        task: data.task.replace(` [${data.image}]`, ` · ${data.image?.split('.')[0] || ''}`),
        op: data.op,
        image: data.image,
        format: data.format,
        ratio,
        speedupDisplay: `${(factor || 1.0).toFixed(2).replace('.', ',')}×`,
        faster,
        timeA: tA,
        timeB: tB,
        bytesA: data.rowA.bytes || 0,
        bytesB: data.rowB.bytes || 0
      });
    }

    // Sort: A fastest on top, down to B fastest
    compared.sort((a, b) => b.ratio - a.ratio);
    return compared;
  }, [longResults, duelImplA, duelImplB]);

  // Summary counts
  const summary = useMemo(() => {
    let winsA = 0;
    let winsB = 0;
    let ties = 0;
    const logRatios: number[] = [];

    const opMap: Record<string, number[]> = {};

    for (const row of duelRows) {
      if (row.faster === 'A') winsA++;
      else if (row.faster === 'B') winsB++;
      else ties++;

      logRatios.push(Math.log(Math.max(0.01, row.ratio)));

      if (!opMap[row.op]) opMap[row.op] = [];
      opMap[row.op].push(row.ratio);
    }

    const geomean = logRatios.length 
      ? Math.exp(logRatios.reduce((a, b) => a + b, 0) / logRatios.length)
      : 1.0;

    const opSummary = Object.entries(opMap).map(([op, ratios]) => {
      const g = Math.exp(ratios.reduce((a, b) => a + Math.log(Math.max(0.01, b)), 0) / ratios.length);
      const isAFaster = g >= 1.0;
      return {
        op,
        isAFaster,
        text: isAFaster ? `A ${(g || 1).toFixed(2).replace('.', ',')}×` : `B ${(1.0 / (g || 1)).toFixed(2).replace('.', ',')}×`
      };
    });

    return {
      winsA,
      winsB,
      ties,
      geomean,
      isAFaster: geomean >= 1.0,
      opSummary
    };
  }, [duelRows]);

  // Width percentage for logarithmic dual-sided bars
  // Center is 50%. Max speedup scale: 100x = 50% width
  const getBarWidthPct = (ratio: number) => {
    const factor = ratio >= 1.0 ? ratio : 1.0 / ratio;
    // log10(1) = 0, log10(100) = 2. Map 0..2 to 0%..46%
    const logVal = Math.log10(Math.max(1.0, factor));
    const pct = (logVal / 2.0) * 46;
    return Math.min(46, Math.max(1, pct));
  };

  return (
    <div id="duel-section" className="bg-[#111418] border border-[#222831] rounded-xl p-4 sm:p-5 mb-6 shadow-sm">
      
      {/* 2-Column Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column (2/3): Duelo - Speedup por tarefa */}
        <div className="lg:col-span-2">
          
          {/* Header & Tabs */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
            <div>
              <h2 className="text-base font-semibold text-[#eceff3]">
                Duelo · speedup por tarefa
              </h2>
              <p className="text-xs text-[#6b7480] mt-0.5">
                Razão do tempo de codec (B ÷ A), escala logarítmica · dados da rodada
              </p>
            </div>

            {/* Metric Selector Tabs */}
            <div className="flex items-center p-0.5 bg-[#0d1013] border border-[#222831] rounded-lg text-xs font-medium">
              <button
                onClick={() => setMetricTab('speedup')}
                className={`px-2.5 py-1 rounded cursor-pointer transition-colors ${
                  metricTab === 'speedup' ? 'bg-[#171b21] text-[#eceff3] border border-[#2e3540]' : 'text-[#6b7480] hover:text-[#a3acb9]'
                }`}
              >
                Speedup
              </button>
              <button
                onClick={() => setMetricTab('throughput')}
                className={`px-2.5 py-1 rounded cursor-pointer transition-colors ${
                  metricTab === 'throughput' ? 'bg-[#171b21] text-[#eceff3] border border-[#2e3540]' : 'text-[#6b7480] hover:text-[#a3acb9]'
                }`}
              >
                Throughput
              </button>
              <button
                onClick={() => setMetricTab('latency')}
                className={`px-2.5 py-1 rounded cursor-pointer transition-colors ${
                  metricTab === 'latency' ? 'bg-[#171b21] text-[#eceff3] border border-[#2e3540]' : 'text-[#6b7480] hover:text-[#a3acb9]'
                }`}
              >
                Latência
              </button>
              <button
                onClick={() => setMetricTab('bytes')}
                className={`px-2.5 py-1 rounded cursor-pointer transition-colors ${
                  metricTab === 'bytes' ? 'bg-[#171b21] text-[#eceff3] border border-[#2e3540]' : 'text-[#6b7480] hover:text-[#a3acb9]'
                }`}
              >
                Tamanho
              </button>
            </div>
          </div>

          {/* Implementation Selectors */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
            
            {/* Selector A */}
            <div className="p-2.5 rounded-lg bg-[#0d1013] border border-[#222831]">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="w-4 h-4 rounded-full bg-[#f4743b] text-white text-[10px] font-mono font-bold flex items-center justify-center">
                  A
                </span>
                <span className="text-xs font-semibold text-[#eceff3]">
                  Implementação A
                </span>
              </div>
              <select
                value={duelImplA}
                onChange={(e) => setDuelImplA(e.target.value)}
                className="w-full text-xs bg-[#111418] border border-[#222831] rounded px-2.5 py-1.5 text-[#eceff3] cursor-pointer focus:outline-none"
              >
                {implementations.map(impl => (
                  <option key={impl.impl_id} value={impl.impl_id}>
                    {impl.language.toUpperCase()} ({impl.tier} · {impl.toolchain} · {impl.lib})
                  </option>
                ))}
              </select>
            </div>

            {/* Selector B */}
            <div className="p-2.5 rounded-lg bg-[#0d1013] border border-[#222831]">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="w-4 h-4 rounded-full bg-[#2ec4e6] text-black text-[10px] font-mono font-bold flex items-center justify-center">
                  B
                </span>
                <span className="text-xs font-semibold text-[#eceff3]">
                  Implementação B
                </span>
              </div>
              <select
                value={duelImplB}
                onChange={(e) => setDuelImplB(e.target.value)}
                className="w-full text-xs bg-[#111418] border border-[#222831] rounded px-2.5 py-1.5 text-[#eceff3] cursor-pointer focus:outline-none"
              >
                {implementations.map(impl => (
                  <option key={impl.impl_id} value={impl.impl_id}>
                    {impl.language.toUpperCase()} ({impl.tier} · {impl.toolchain} · {impl.lib})
                  </option>
                ))}
              </select>
            </div>

          </div>

          {/* Scale Axis Indicator */}
          <div className="relative w-full h-7 mb-2 text-[10px] font-mono text-[#6b7480] border-b border-[#222831]">
            <div className="absolute left-2 bottom-1.5 flex items-center gap-1 text-[#2ec4e6]">
              <span>← B mais rápido</span>
            </div>
            <div className="absolute right-2 bottom-1.5 flex items-center gap-1 text-[#f4743b]">
              <span>A mais rápido →</span>
            </div>
            <div className="absolute left-1/2 -translate-x-1/2 bottom-1.5 font-bold text-[#eceff3]">
              1×
            </div>
          </div>

          {/* Dual-Sided Bar Chart */}
          <div className="space-y-1.5 max-h-[560px] overflow-y-auto pr-1">
            {duelRows.map(row => {
              const isA = row.faster === 'A';
              const isB = row.faster === 'B';
              const barWidth = getBarWidthPct(row.ratio);

              return (
                <div key={row.taskId} className="group relative flex items-center h-6 hover:bg-[#171b21]/40 rounded px-1 transition-colors">
                  
                  {/* Task Title */}
                  <span className="absolute left-2 z-10 text-[11px] text-[#eceff3] font-medium truncate max-w-[200px] sm:max-w-xs group-hover:text-white pointer-events-none">
                    {row.task}
                  </span>

                  {/* Left Side (B is faster) */}
                  <div className="flex-1 flex justify-end items-center h-full relative pr-1">
                    {isB && (
                      <div 
                        className="h-4 rounded-l transition-all"
                        style={{
                          width: `${barWidth}%`,
                          backgroundColor: colorB
                        }}
                      />
                    )}
                    {isB && (
                      <span className="mr-2 text-[10px] font-mono font-semibold text-[#2ec4e6]">
                        {row.speedupDisplay}
                      </span>
                    )}
                  </div>

                  {/* Center Line Axis */}
                  <div className="w-px h-5 bg-[#2e3540] shrink-0" />

                  {/* Right Side (A is faster) */}
                  <div className="flex-1 flex justify-start items-center h-full relative pl-1">
                    {isA && (
                      <div 
                        className="h-4 rounded-r transition-all"
                        style={{
                          width: `${barWidth}%`,
                          backgroundColor: colorA
                        }}
                      />
                    )}
                    {isA && (
                      <span className="ml-2 text-[10px] font-mono font-semibold text-[#f4743b]">
                        {row.speedupDisplay}
                      </span>
                    )}
                    {row.faster === 'TIE' && (
                      <span className="ml-2 text-[10px] font-mono text-[#6b7480]">
                        empate (1,0×)
                      </span>
                    )}
                  </div>

                </div>
              );
            })}
          </div>

        </div>

        {/* Right Column (1/3): Placar do Duelo & Qualidade Equivalente */}
        <div className="flex flex-col gap-5 border-t lg:border-t-0 lg:border-l border-[#222831] pt-4 lg:pt-0 lg:pl-6">
          
          {/* Placar do Duelo */}
          <div>
            <h3 className="text-sm font-semibold text-[#eceff3] mb-3">
              Placar do duelo
            </h3>

            {/* Split Bar */}
            <div className="bg-[#0d1013] border border-[#222831] rounded-xl p-3.5">
              <div className="flex items-center justify-between text-xs font-mono font-bold mb-1.5">
                <span className="text-[#f4743b]">A: {summary.winsA} vitórias</span>
                {summary.ties > 0 && <span className="text-[#6b7480]">{summary.ties} empate</span>}
                <span className="text-[#2ec4e6]">B: {summary.winsB} vitórias</span>
              </div>

              {/* Progress split */}
              <div className="h-3 w-full bg-[#111418] rounded-full overflow-hidden flex">
                <div 
                  className="h-full bg-[#f4743b] transition-all" 
                  style={{ width: `${(summary.winsA / (duelRows.length || 1)) * 100}%` }} 
                />
                <div 
                  className="h-full bg-[#6b7480]" 
                  style={{ width: `${(summary.ties / (duelRows.length || 1)) * 100}%` }} 
                />
                <div 
                  className="h-full bg-[#2ec4e6] transition-all" 
                  style={{ width: `${(summary.winsB / (duelRows.length || 1)) * 100}%` }} 
                />
              </div>

              <div className="mt-3 text-center">
                <span className="text-xl font-bold font-mono text-[#eceff3]">
                  {((summary.isAFaster ? summary.geomean : 1.0 / (summary.geomean || 1)) || 1.0).toFixed(2).replace('.', ',')}×
                </span>
                <p className="text-[11px] text-[#a3acb9] mt-0.5">
                  média geométrica · {summary.isAFaster ? 'A mais rápido' : 'B mais rápido'}
                </p>
              </div>
            </div>
          </div>

          {/* Por Operação */}
          <div>
            <h4 className="text-xs font-semibold text-[#eceff3] mb-2 uppercase tracking-wider font-mono">
              Por operação
            </h4>
            <div className="grid grid-cols-2 gap-2 text-xs font-mono">
              {summary.opSummary.map(item => (
                <div key={item.op} className="p-2 rounded bg-[#0d1013] border border-[#222831] flex items-center justify-between">
                  <span className="text-[#a3acb9] capitalize">{item.op}</span>
                  <span className={item.isAFaster ? 'text-[#f4743b] font-bold' : 'text-[#2ec4e6] font-bold'}>
                    {item.text}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Qualidade Equivalente (PSNR igual) */}
          <div className="border-t border-[#222831] pt-4">
            <h4 className="text-xs font-semibold text-[#eceff3]">
              Qualidade equivalente (PSNR igual)
            </h4>
            <p className="text-[11px] text-[#6b7480] mt-0.5 leading-snug">
              B fixa q=75; A usa o menor q que iguala ou supera o PSNR de B.
            </p>

            <div className="mt-3 space-y-2">
              {equalQuality && equalQuality.slice(0, 4).map((eq: any, i: number) => {
                const isAFaster = eq.winner === 'Rust';
                const isBFaster = eq.winner === 'Go';
                const speedupVal = eq.speedup ?? 1.0;
                const bytesRatioVal = eq.bytes_ratio ?? 1.0;
                const psnrVal = eq.rust_psnr_db ?? eq.psnr_rust ?? 40.0;

                return (
                  <div key={i} className="p-2.5 rounded-lg bg-[#0d1013] border border-[#222831] text-xs">
                    <div className="flex items-center justify-between text-[#eceff3] font-medium">
                      <span>{eq.task}</span>
                      <span className={`font-mono font-bold ${
                        isAFaster ? 'text-[#f4743b]' : isBFaster ? 'text-[#2ec4e6]' : 'text-[#8a93a0]'
                      }`}>
                        {isAFaster ? `A ${speedupVal.toFixed(2).replace('.', ',')}×` : isBFaster ? `B ${speedupVal.toFixed(2).replace('.', ',')}×` : `empate ${speedupVal.toFixed(2).replace('.', ',')}×`}
                      </span>
                    </div>

                    <div className="mt-1 flex items-center justify-between text-[11px] font-mono text-[#6b7480]">
                      <span>tam. B/A {bytesRatioVal.toFixed(2).replace('.', ',')}×</span>
                      <span>PSNR: {typeof psnrVal === 'number' ? psnrVal.toFixed(1) : psnrVal} dB</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

        </div>

      </div>

    </div>
  );
}
