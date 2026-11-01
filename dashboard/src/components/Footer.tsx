'use client';

import React from 'react';
import { Cpu, Scale, ShieldCheck, GitBranch } from 'lucide-react';
import { useData } from '../context/DataContext';

export default function Footer() {
  const { metadata } = useData();
  const env = metadata?.environment;
  const iterations = metadata?.iterations;
  const warmup = metadata?.warmup;

  return (
    <footer className="w-full border-t border-[var(--arena-border)] py-12 mt-12 bg-[var(--arena-surface)] text-xs text-[var(--arena-text-secondary)] transition-colors">
      <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
        
        {/* 3 Metodology Columns */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          
          {/* Col 1: Métrica Primária */}
          <div className="p-4 rounded-xl bg-[var(--arena-canvas)] border border-[var(--arena-border)] space-y-2">
            <div className="flex items-center gap-2 text-[var(--arena-text-primary)] font-bold">
              <Cpu className="w-4 h-4 text-[#C9501C] dark:text-[#E0703A]" />
              <h4>01. Métrica Primária (Tempo de Codec)</h4>
            </div>
            <p className="text-[11px] leading-relaxed text-[var(--arena-text-secondary)]">
              Mediana do tempo de codec sobre {iterations ?? '-'} repetições, depois de {warmup ?? '-'} execuções de aquecimento descartadas. O benchmark exclui estritamente I/O de disco, alocando os buffers em memória para medir a eficiência real dos algoritmos na CPU.
            </p>
          </div>

          {/* Col 2: Critério de Empate */}
          <div className="p-4 rounded-xl bg-[var(--arena-canvas)] border border-[var(--arena-border)] space-y-2">
            <div className="flex items-center gap-2 text-[var(--arena-text-primary)] font-bold">
              <Scale className="w-4 h-4 text-[#9A7B00] dark:text-[#B38D1E]" />
              <h4>02. Critério de Empate Estatístico</h4>
            </div>
            <p className="text-[11px] leading-relaxed text-[var(--arena-text-secondary)]">
              Sobreposição estrita dos intervalos interquartis [p25, p75]: <code className="font-mono text-[10px] text-[var(--arena-text-primary)]">max(p25_A, p25_B) ≤ min(p75_A, p75_B)</code>. Quando os intervalos se tocam, a diferença é estatisticamente indistinguível do jitter de hardware.
            </p>
          </div>

          {/* Col 3: Validação & Pureza */}
          <div className="p-4 rounded-xl bg-[var(--arena-canvas)] border border-[var(--arena-border)] space-y-2">
            <div className="flex items-center gap-2 text-[var(--arena-text-primary)] font-bold">
              <ShieldCheck className="w-4 h-4 text-[#2E8B3E] dark:text-[#3DD68C]" />
              <h4>03. Validação & Pureza de Código</h4>
            </div>
            <p className="text-[11px] leading-relaxed text-[var(--arena-text-secondary)]">
              Validação bit-exact para formatos lossless contra decodificadores de referência e métrica PSNR (dB) para lossy. Classificação explícita entre implementações nativas puras (sem FFI) e híbridas (wrappers C/C++).
            </p>
          </div>

        </div>

        {/* Provenance & Copyright */}
        <div className="pt-6 border-t border-[var(--arena-border)]/60 flex flex-col sm:flex-row items-center justify-between gap-3 text-[11px] font-mono text-[var(--arena-text-muted)]">
          <div className="flex items-center gap-2">
            <GitBranch className="w-3.5 h-3.5" />
            <span>Image Processor Arena · Ficha de Cronometragem Oficial · Licença AGPL-3.0-or-later</span>
          </div>

          <div>
            <span>
              Ambiente: {env?.cpu ?? '-'} · {env?.cpu_count ?? '-'} CPUs lógicas · {metadata?.collected_at ?? '-'}
            </span>
          </div>
        </div>

      </div>
    </footer>
  );
}
