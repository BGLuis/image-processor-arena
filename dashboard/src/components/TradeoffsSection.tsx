'use client';

import React, { useState, useMemo } from 'react';
import { Scale, CheckCircle2, AlertCircle, Info, Sparkles } from 'lucide-react';
import { useData } from '../context/DataContext';

const langColors: Record<string, string> = {
  go: 'var(--lang-go)',
  rust: 'var(--lang-rust)',
};

export default function TradeoffsSection() {
  const { longResults, equalQuality } = useData();

  const [modeFilter, setModeFilter] = useState<'all' | 'lossy' | 'lossless'>('all');
  const [hoveredPoint, setHoveredPoint] = useState<any | null>(null);

  // 25 tasks of encode and transcode
  const scatterData = useMemo(() => {
    return longResults.filter(r => {
      const isEncodeOrTranscode = r.op === 'encode' || r.op === 'transcode';
      if (!isEncodeOrTranscode) return false;
      if (r.bytes <= 0 || r.codec_median_ms <= 0) return false;
      if (modeFilter !== 'all' && r.mode !== modeFilter) return false;
      return true;
    });
  }, [longResults, modeFilter]);

  // Coordinate scales for scatter plot (Dual logarithmic)
  // X = bytes: 1000 to 200000 bytes (1 KB to 200 KB)
  // Y = codec_median_ms: 0.5 to 1500 ms
  const minBytes = 1000;
  const maxBytes = 220000;
  const minTime = 0.4;
  const maxTime = 1400;

  const logMinBytes = Math.log10(minBytes);
  const logMaxBytes = Math.log10(maxBytes);
  const logMinTime = Math.log10(minTime);
  const logMaxTime = Math.log10(maxTime);

  // SVG dimensions
  const svgWidth = 600;
  const svgHeight = 360;
  const padLeft = 55;
  const padRight = 30;
  const padTop = 30;
  const padBottom = 45;

  const plotWidth = svgWidth - padLeft - padRight;
  const plotHeight = svgHeight - padTop - padBottom;

  const getX = (bytes: number) => {
    const clamped = Math.max(minBytes, Math.min(maxBytes, bytes));
    const log = Math.log10(clamped);
    return padLeft + ((log - logMinBytes) / (logMaxBytes - logMinBytes)) * plotWidth;
  };

  const getY = (time: number) => {
    const clamped = Math.max(minTime, Math.min(maxTime, time));
    const log = Math.log10(clamped);
    // Y inverted in SVG (top is high time, bottom is low time)
    return padTop + plotHeight - ((log - logMinTime) / (logMaxTime - logMinTime)) * plotHeight;
  };

  // Center crosshair dividing into 4 quadrants: median bytes ~ 25 KB, median time ~ 35 ms
  const crosshairBytes = 25000;
  const crosshairTime = 35;
  const crosshairX = getX(crosshairBytes);
  const crosshairY = getY(crosshairTime);

  return (
    <section id="tradeoffs" className="mb-10 scroll-mt-28">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold text-[#C9501C] dark:text-[#E0703A] uppercase tracking-wider">
              Seção 03
            </span>
            <h2 className="text-xl font-bold tracking-tight text-[var(--arena-text-primary)]">
              Velocidade Não É Tudo: Trade-offs de Compressão
            </h2>
          </div>
          <p className="text-xs text-[var(--arena-text-secondary)] mt-1">
            Tempo de execução versus tamanho de arquivo gerado e qualidade perceptual (PSNR equivalente).
          </p>
        </div>

        {/* Filter Toggle */}
        <div className="flex items-center p-0.5 bg-[var(--arena-surface)] border border-[var(--arena-border)] rounded-lg text-xs font-mono">
          <button
            onClick={() => setModeFilter('all')}
            className={`px-2.5 py-1 rounded cursor-pointer transition-colors ${
              modeFilter === 'all' ? 'bg-[var(--arena-canvas)] text-[var(--arena-text-primary)] font-bold shadow-xs' : 'text-[var(--arena-text-secondary)] hover:text-[var(--arena-text-primary)]'
            }`}
          >
            Todas (25 tarefas)
          </button>
          <button
            onClick={() => setModeFilter('lossy')}
            className={`px-2.5 py-1 rounded cursor-pointer transition-colors ${
              modeFilter === 'lossy' ? 'bg-[var(--arena-canvas)] text-[var(--arena-text-primary)] font-bold shadow-xs' : 'text-[var(--arena-text-secondary)] hover:text-[var(--arena-text-primary)]'
            }`}
          >
            Lossy
          </button>
          <button
            onClick={() => setModeFilter('lossless')}
            className={`px-2.5 py-1 rounded cursor-pointer transition-colors ${
              modeFilter === 'lossless' ? 'bg-[var(--arena-canvas)] text-[var(--arena-text-primary)] font-bold shadow-xs' : 'text-[var(--arena-text-secondary)] hover:text-[var(--arena-text-primary)]'
            }`}
          >
            Lossless
          </button>
        </div>
      </div>

      {/* 2-Column Grid: Left = Scatter Plot (4 quadrants), Right = Equal Quality Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left Column (7 cols): Dual Logarithmic Scatter Plot */}
        <div className="lg:col-span-7 bg-[var(--arena-surface)] border border-[var(--arena-border)] rounded-xl p-4 sm:p-5 flex flex-col justify-between shadow-xs">
          
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-bold text-[var(--arena-text-primary)]">
                Dispersão Tempo × Tamanho (25 Tarefas de Encode)
              </h3>
              <span className="text-[10px] font-mono text-[var(--arena-text-muted)]">
                Eixos duplamente logarítmicos
              </span>
            </div>
            <p className="text-xs text-[var(--arena-text-secondary)] mb-4">
              O ponto ideal fica no quadrante inferior esquerdo: menor tempo e menor arquivo compactado.
            </p>

            {/* SVG Scatter Plot */}
            <div className="relative w-full overflow-hidden bg-[var(--arena-canvas)] rounded-lg border border-[var(--arena-border)] p-2">
              <svg 
                viewBox={`0 0 ${svgWidth} ${svgHeight}`} 
                className="w-full h-auto max-h-[420px] select-none"
              >
                {/* Quadrant Background Tints */}
                {/* Q3: Bottom-Left (Ideal / Ótimo) */}
                <rect
                  x={padLeft}
                  y={crosshairY}
                  width={crosshairX - padLeft}
                  height={padTop + plotHeight - crosshairY}
                  fill="rgba(46, 139, 62, 0.08)"
                />
                {/* Q2: Top-Right (Pior dos mundos) */}
                <rect
                  x={crosshairX}
                  y={padTop}
                  width={padLeft + plotWidth - crosshairX}
                  height={crosshairY - padTop}
                  fill="rgba(201, 80, 28, 0.06)"
                />

                {/* Quadrant Labels */}
                <text x={padLeft + 8} y={padTop + 16} className="text-[10px] font-mono fill-[var(--arena-text-muted)] font-semibold">
                  Lento & Compacto
                </text>
                <text x={padLeft + plotWidth - 10} y={padTop + 16} textAnchor="end" className="text-[10px] font-mono fill-[var(--arena-text-muted)] font-semibold">
                  Lento & Grande (Pior)
                </text>
                <text x={padLeft + 8} y={padTop + plotHeight - 8} className="text-[10px] font-mono fill-[#2E8B3E] dark:fill-[#3DD68C] font-bold">
                  ★ Ideal (Rápido & Compacto)
                </text>
                <text x={padLeft + plotWidth - 10} y={padTop + plotHeight - 8} textAnchor="end" className="text-[10px] font-mono fill-[var(--arena-text-muted)] font-semibold">
                  Rápido & Grande
                </text>

                {/* Crosshairs dividing quadrants */}
                <line
                  x1={crosshairX}
                  y1={padTop}
                  x2={crosshairX}
                  y2={padTop + plotHeight}
                  stroke="var(--arena-border-strong)"
                  strokeWidth={1}
                  strokeDasharray="3,3"
                />
                <line
                  x1={padLeft}
                  y1={crosshairY}
                  x2={padLeft + plotWidth}
                  y2={crosshairY}
                  stroke="var(--arena-border-strong)"
                  strokeWidth={1}
                  strokeDasharray="3,3"
                />

                {/* X Axis Grid & Ticks */}
                {[2000, 10000, 50000, 150000].map(val => {
                  const x = getX(val);
                  return (
                    <g key={val}>
                      <line x1={x} y1={padTop} x2={x} y2={padTop + plotHeight} stroke="var(--arena-border)" strokeWidth={0.5} strokeDasharray="2,2" />
                      <text x={x} y={padTop + plotHeight + 14} textAnchor="middle" className="text-[9px] font-mono fill-[var(--arena-text-muted)]">
                        {val >= 1000 ? `${val / 1000} KB` : `${val} B`}
                      </text>
                    </g>
                  );
                })}

                {/* Y Axis Grid & Ticks */}
                {[1, 10, 100, 1000].map(val => {
                  const y = getY(val);
                  return (
                    <g key={val}>
                      <line x1={padLeft} y1={y} x2={padLeft + plotWidth} y2={y} stroke="var(--arena-border)" strokeWidth={0.5} strokeDasharray="2,2" />
                      <text x={padLeft - 6} y={y + 3} textAnchor="end" className="text-[9px] font-mono fill-[var(--arena-text-muted)]">
                        {val} ms
                      </text>
                    </g>
                  );
                })}

                {/* Axis Labels */}
                <text
                  x={padLeft + plotWidth / 2}
                  y={padTop + plotHeight + 32}
                  textAnchor="middle"
                  className="text-[10px] font-mono fill-[var(--arena-text-secondary)] font-semibold"
                >
                  Tamanho de Saída (KB, escala logarítmica) →
                </text>
                <text
                  transform={`rotate(-90 ${padLeft - 36} ${padTop + plotHeight / 2})`}
                  x={padLeft - 36}
                  y={padTop + plotHeight / 2}
                  textAnchor="middle"
                  className="text-[10px] font-mono fill-[var(--arena-text-secondary)] font-semibold"
                >
                  Tempo de Codec (ms, escala logarítmica) →
                </text>

                {/* Scatter Dots */}
                {scatterData.map((d, idx) => {
                  const cx = getX(d.bytes);
                  const cy = getY(d.codec_median_ms);
                  const isHovered = hoveredPoint?.task_id === d.task_id && hoveredPoint?.impl_id === d.impl_id;

                  return (
                    <circle
                      key={`${d.task_id}-${d.impl_id}-${idx}`}
                      cx={cx}
                      cy={cy}
                      r={isHovered ? 5.5 : 3.5}
                      style={{ fill: langColors[d.language] || 'var(--lang-rust)' }}
                      className="cursor-pointer transition-all hover:stroke-[var(--arena-canvas)] hover:stroke-2 opacity-85 hover:opacity-100"
                      onMouseEnter={() => setHoveredPoint(d)}
                      onMouseLeave={() => setHoveredPoint(null)}
                    />
                  );
                })}
              </svg>

              {/* Hover Tooltip Overlay */}
              {hoveredPoint && (
                <div className="absolute top-3 right-3 bg-[var(--arena-surface)] border border-[var(--arena-border-strong)] rounded-lg p-2.5 text-xs shadow-lg font-mono pointer-events-none max-w-xs z-20">
                  <div className="font-bold text-[var(--arena-text-primary)] truncate">
                    {hoveredPoint.task}
                  </div>
                  <div className="text-[11px] text-[var(--arena-text-secondary)] mt-0.5">
                    {hoveredPoint.language.toUpperCase()} ({hoveredPoint.tier} · {hoveredPoint.lib})
                  </div>
                  <div className="mt-2 pt-1.5 border-t border-[var(--arena-border)]/60 grid grid-cols-2 gap-2 text-[10px]">
                    <div>
                      <span className="text-[var(--arena-text-muted)]">Tempo: </span>
                      <span className="font-bold text-[var(--arena-text-primary)]">
                        {hoveredPoint.codec_median_ms.toFixed(1)} ms
                      </span>
                    </div>
                    <div>
                      <span className="text-[var(--arena-text-muted)]">Tamanho: </span>
                      <span className="font-bold text-[var(--arena-text-primary)]">
                        {(hoveredPoint.bytes / 1024).toFixed(1)} KB
                      </span>
                    </div>
                    {hoveredPoint.psnr_db && (
                      <div className="col-span-2 text-[#2E8B3E] dark:text-[#3DD68C]">
                        PSNR: {hoveredPoint.psnr_db.toFixed(1)} dB
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Scatter Legend */}
          <div className="mt-4 pt-3 border-t border-[var(--arena-border)]/60 flex items-center justify-between text-[11px] font-mono text-[var(--arena-text-muted)]">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-[#C9501C] dark:bg-[#E0703A]" /> Rust
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-[#0086A3] dark:bg-[#25A3B5]" /> Go
              </span>
            </div>
            <span>{scatterData.length} pontos plotados</span>
          </div>

        </div>

        {/* Right Column (5 cols): 4 Equal Quality Cards (PSNR Igual) */}
        <div className="lg:col-span-5 flex flex-col justify-between bg-[var(--arena-surface)] border border-[var(--arena-border)] rounded-xl p-4 sm:p-5 shadow-xs">
          
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-1.5">
                <Scale className="w-4 h-4 text-[#2E8B3E] dark:text-[#3DD68C]" />
                <h3 className="text-sm font-bold text-[var(--arena-text-primary)]">
                  Qualidade Equivalente (PSNR Igual)
                </h3>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[#2E8B3E]/15 text-[#2E8B3E] dark:text-[#3DD68C] font-semibold border border-[#2E8B3E]/30">
                4 Tarefas Calibradas
              </span>
            </div>
            <p className="text-xs text-[var(--arena-text-secondary)] mb-4">
              Go fixa q=75; Rust busca o menor q que iguala ou supera o PSNR de Go.
            </p>

            {/* 4 Cards Grid */}
            <div className="space-y-3">
              {equalQuality && equalQuality.map((item, idx) => {
                const goTime = item.go_time_ms.median;
                const rustTime = item.rust_time_ms.median;
                const maxTime = Math.max(goTime, rustTime);

                const goBytes = item.go_bytes;
                const rustBytes = item.rust_bytes;
                const maxBytes = Math.max(goBytes, rustBytes);

                const isGoFaster = item.winner === 'Go';
                const isRustFaster = item.winner === 'Rust';
                const isTie = item.winner === 'Empate';

                return (
                  <div 
                    key={idx}
                    className="p-3 rounded-lg bg-[var(--arena-canvas)] border border-[var(--arena-border)] hover:border-[var(--arena-border-strong)] transition-all text-xs"
                  >
                    {/* Header: Task name and PSNR Target */}
                    <div className="flex items-center justify-between font-medium">
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-[#C9501C] dark:bg-[#E0703A]" />
                        <span className="font-semibold text-[var(--arena-text-primary)] truncate max-w-[210px]" title={item.task}>
                          {item.task}
                        </span>
                      </div>
                      <span className="text-[11px] font-mono text-[var(--arena-text-secondary)]">
                        Alvo: <strong>{item.target_psnr_db.toFixed(1)} dB</strong>
                      </span>
                    </div>

                    {/* Parameters row: q setting & actual PSNR */}
                    <div className="mt-2 text-[10px] font-mono text-[var(--arena-text-muted)] flex items-center justify-between">
                      <span>Go: q={item.go_q} ({(item.go_psnr_db ?? 0).toFixed(1)} dB)</span>
                      <span>Rust: q={item.rust_q} ({(item.rust_psnr_db ?? 0).toFixed(1)} dB)</span>
                    </div>

                    {/* Bar comparison 1: Execution Time */}
                    <div className="mt-2 pt-2 border-t border-[var(--arena-border)]/50">
                      <div className="flex items-center justify-between text-[11px] font-mono mb-1">
                        <span className="text-[var(--arena-text-secondary)]">Tempo de Codec</span>
                        <span className={`font-bold ${
                          isRustFaster ? 'text-[#C9501C] dark:text-[#E0703A]' : isGoFaster ? 'text-[#0086A3] dark:text-[#25A3B5]' : 'text-[#9A7B00] dark:text-[#F5A524]'
                        }`}>
                          {isRustFaster ? `Rust ${item.speedup.toFixed(2).replace('.', ',')}× mais rápido` : isGoFaster ? `Go ${item.speedup.toFixed(2).replace('.', ',')}× mais rápido` : `Empate (${item.speedup.toFixed(2).replace('.', ',')}×)`}
                        </span>
                      </div>

                      {/* Go time bar */}
                      <div className="flex items-center gap-2 text-[10px] font-mono mb-1">
                        <span className="w-8 text-[#0086A3] dark:text-[#25A3B5] font-semibold">Go</span>
                        <div className="flex-1 h-2 bg-[var(--arena-surface)] rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-[#0086A3] dark:bg-[#25A3B5] rounded-full" 
                            style={{ width: `${(goTime / maxTime) * 100}%` }} 
                          />
                        </div>
                        <span className="w-16 text-right text-[var(--arena-text-primary)]">{goTime.toFixed(1)} ms</span>
                      </div>

                      {/* Rust time bar */}
                      <div className="flex items-center gap-2 text-[10px] font-mono">
                        <span className="w-8 text-[#C9501C] dark:text-[#E0703A] font-semibold">Rust</span>
                        <div className="flex-1 h-2 bg-[var(--arena-surface)] rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-[#C9501C] dark:bg-[#E0703A] rounded-full" 
                            style={{ width: `${(rustTime / maxTime) * 100}%` }} 
                          />
                        </div>
                        <span className="w-16 text-right text-[var(--arena-text-primary)]">{rustTime.toFixed(1)} ms</span>
                      </div>
                    </div>

                    {/* Bar comparison 2: Output File Size */}
                    <div className="mt-2 pt-1.5 border-t border-[var(--arena-border)]/50">
                      <div className="flex items-center justify-between text-[11px] font-mono mb-1">
                        <span className="text-[var(--arena-text-secondary)]">Tamanho do Arquivo</span>
                        <span className="font-bold text-[var(--arena-text-primary)]">
                          {item.bytes_ratio >= 1.0 
                            ? `Rust ${(item.bytes_ratio).toFixed(2).replace('.', ',')}× mais compacto` 
                            : `Go ${(1.0 / item.bytes_ratio).toFixed(2).replace('.', ',')}× mais compacto`}
                        </span>
                      </div>

                      {/* Go bytes bar */}
                      <div className="flex items-center gap-2 text-[10px] font-mono mb-1">
                        <span className="w-8 text-[#0086A3] dark:text-[#25A3B5] font-semibold">Go</span>
                        <div className="flex-1 h-2 bg-[var(--arena-surface)] rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-[#0086A3] dark:bg-[#25A3B5] rounded-full" 
                            style={{ width: `${(goBytes / maxBytes) * 100}%` }} 
                          />
                        </div>
                        <span className="w-16 text-right text-[var(--arena-text-primary)]">{(goBytes / 1024).toFixed(1)} KB</span>
                      </div>

                      {/* Rust bytes bar */}
                      <div className="flex items-center gap-2 text-[10px] font-mono">
                        <span className="w-8 text-[#C9501C] dark:text-[#E0703A] font-semibold">Rust</span>
                        <div className="flex-1 h-2 bg-[var(--arena-surface)] rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-[#C9501C] dark:bg-[#E0703A] rounded-full" 
                            style={{ width: `${(rustBytes / maxBytes) * 100}%` }} 
                          />
                        </div>
                        <span className="w-16 text-right text-[var(--arena-text-primary)]">{(rustBytes / 1024).toFixed(1)} KB</span>
                      </div>
                    </div>

                  </div>
                );
              })}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-[var(--arena-border)]/60 text-[10px] font-mono text-[var(--arena-text-muted)] leading-relaxed">
            Metodologia: Fixa o target PSNR na métrica perceptual. Em AVIF, o codec de Rust atinge a mesma qualidade gerando arquivos significativamente mais compactos.
          </div>

        </div>

      </div>

    </section>
  );
}
