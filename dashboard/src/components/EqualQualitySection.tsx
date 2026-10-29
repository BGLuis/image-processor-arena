'use client';

import React from 'react';
import { Scale, CheckCircle2, Award } from 'lucide-react';
import { useData } from '../context/DataContext';

export default function EqualQualitySection() {
  const { equalQuality } = useData();

  if (!equalQuality || !equalQuality.length) return null;

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 my-6 backdrop-blur-sm">
      <div className="flex items-center gap-2 mb-2">
        <Scale className="w-5 h-5 text-amber-400" />
        <h2 className="text-base sm:text-lg font-bold text-white">
          Comparação a Qualidade Equivalente (Equal PSNR)
        </h2>
      </div>
      <p className="text-xs text-slate-400 mb-4 max-w-3xl">
        O mesmo <code className="text-cyan-400">q</code> não produz o mesmo PSNR nos dois motores. 
        Aqui, o alvo de PSNR é fixado no valor do Go (q=75) e o Rust utiliza o menor <code className="text-orange-400">q</code> que 
        iguala ou supera essa fidelidade visual.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {equalQuality.map((item, idx) => {
          const isRustWinner = item.winner === 'Rust';
          const isGoWinner = item.winner === 'Go';

          return (
            <div 
              key={idx} 
              className="bg-slate-950 border border-slate-800/80 rounded-xl p-4 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-3">
                  <h3 className="font-semibold text-sm text-slate-200">
                    {item.task}
                  </h3>
                  <span className={`px-2 py-0.5 text-xs font-bold rounded-full ${
                    isRustWinner 
                      ? 'bg-orange-950 text-orange-400 border border-orange-800' 
                      : isGoWinner
                      ? 'bg-cyan-950 text-cyan-400 border border-cyan-800'
                      : 'bg-purple-950 text-purple-400 border border-purple-800'
                  }`}>
                    {item.winner} ({item.speedup.toFixed(2)}x)
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs mb-3">
                  {/* Go Card */}
                  <div className="bg-slate-900/70 p-2.5 rounded-lg border border-cyan-950">
                    <span className="font-bold text-cyan-400 block mb-1">Go Puro (q={item.go_q})</span>
                    <div className="space-y-0.5 text-slate-300">
                      <div>Tempo: <span className="font-mono text-white">{item.go_time_ms.median.toFixed(2)} ms</span></div>
                      <div>PSNR: <span className="font-mono text-white">{item.psnr_go.toFixed(2)} dB</span></div>
                      <div>Tamanho: <span className="font-mono text-white">{(item.go_bytes / 1024).toFixed(1)} KB</span></div>
                    </div>
                  </div>

                  {/* Rust Card */}
                  <div className="bg-slate-900/70 p-2.5 rounded-lg border border-orange-950">
                    <span className="font-bold text-orange-400 block mb-1">Rust Puro (q={item.rust_q})</span>
                    <div className="space-y-0.5 text-slate-300">
                      <div>Tempo: <span className="font-mono text-white">{item.rust_time_ms.median.toFixed(2)} ms</span></div>
                      <div>PSNR: <span className="font-mono text-white">{item.psnr_rust.toFixed(2)} dB</span></div>
                      <div>Tamanho: <span className="font-mono text-white">{(item.rust_bytes / 1024).toFixed(1)} KB</span></div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="text-[11px] text-slate-400 pt-2 border-t border-slate-900 flex items-center justify-between">
                <span>Alvo PSNR: <strong className="text-slate-200">{item.target_psnr_db.toFixed(2)} dB</strong></span>
                <span>Razão Tamanho (Go/Rust): <strong className="text-slate-200">{item.bytes_ratio.toFixed(2)}x</strong></span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
