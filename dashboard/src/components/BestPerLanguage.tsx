'use client';

import React from 'react';
import { useData } from '../context/DataContext';

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

export default function BestPerLanguage() {
  const { implementations } = useData();

  const languages = ['rust', 'zig', 'go', 'swift', 'csharp', 'java'];

  const bestByLang = languages.map(lang => {
    const variants = implementations.filter(i => i.language === lang);
    variants.sort((a, b) => a.score - b.score);
    const best = variants[0] || null;
    return {
      lang,
      best,
      variants
    };
  }).filter(item => item.best !== null);

  // Position on a 1x to 10x log scale (0% at 1x, 100% at 10x)
  const getLogPositionPercent = (score: number) => {
    const minVal = 1.0;
    const maxVal = 10.0;
    const val = typeof score === 'number' ? score : 1.0;
    const clamped = Math.min(Math.max(val, minVal), maxVal);
    const pct = ((Math.log10(clamped) - Math.log10(minVal)) / (Math.log10(maxVal) - Math.log10(minVal))) * 100;
    return Math.max(3, Math.min(97, pct));
  };

  return (
    <div className="mb-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold tracking-tight text-[#eceff3]">
          Melhor por linguagem
        </h2>
        <span className="text-[11px] font-mono text-[#6b7480]">
          pontos = variantes da linguagem · escala log 1×–10×
        </span>
      </div>

      {/* Grid of 6 language cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {bestByLang.map(({ lang, best, variants }) => {
          if (!best) return null;
          const color = langColors[lang] || '#a3acb9';
          const displayName = langDisplayNames[lang] || lang;
          const scoreDisplay = typeof best.score === 'number' ? best.score.toFixed(2).replace('.', ',') : '1,00';
          
          return (
            <div 
              key={lang}
              className="bg-[#111418] border border-[#222831] hover:border-[#2e3540] rounded-xl p-3 flex flex-col justify-between transition-colors shadow-sm"
            >
              <div>
                {/* Top: Dot + Name + Rank badge */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span 
                      className="w-2 h-2 rounded-full" 
                      style={{ backgroundColor: color }} 
                    />
                    <span className="text-xs font-semibold text-[#eceff3]">
                      {displayName}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-[#a3acb9] px-1.5 py-0.2 rounded bg-[#0d1013] border border-[#222831]">
                    #{best.rank}
                  </span>
                </div>

                {/* Score */}
                <div className="mt-2.5">
                  <span className="text-xl font-bold font-mono text-[#eceff3]">
                    {scoreDisplay}×
                  </span>
                </div>

                {/* Subtitle / variant description */}
                <p className="text-[11px] text-[#a3acb9] mt-0.5 truncate" title={`${best.tier} · ${best.lib}`}>
                  {best.tier === 'hybrid' ? 'hybrid' : best.toolchain} · {best.lib ? best.lib.replace(' · padrão', '') : ''}
                </p>
              </div>

              {/* Logarithmic variant dot strip */}
              <div className="mt-4 pt-2">
                <div className="relative w-full h-3 flex items-center">
                  {/* Axis bar */}
                  <div className="w-full h-px bg-[#222831]" />

                  {/* Variant dots */}
                  {variants.map((v, i) => {
                    const isBest = i === 0;
                    const left = getLogPositionPercent(v.score);
                    const vScore = typeof v.score === 'number' ? v.score.toFixed(2) : '1.00';
                    return (
                      <div
                        key={v.impl_id}
                        className={`absolute -translate-x-1/2 rounded-full transition-transform hover:scale-125 ${
                          isBest 
                            ? 'w-2.5 h-2.5 ring-2 ring-[#111418]' 
                            : 'w-1.5 h-1.5 opacity-60'
                        }`}
                        style={{
                          left: `${left}%`,
                          backgroundColor: color,
                        }}
                        title={`${v.toolchain} (${v.lib}): ${vScore}x`}
                      />
                    );
                  })}
                </div>
              </div>

            </div>
          );
        })}
      </div>
    </div>
  );
}
