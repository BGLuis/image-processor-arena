'use client';

import React, { useState, useEffect } from 'react';
import { Terminal, Play, Check, Database, Zap } from 'lucide-react';
import { useData } from '../context/DataContext';

interface Preset {
  id: string;
  name: string;
  query: string;
}

const presets: Preset[] = [
  {
    id: 'ranking',
    name: 'Ranking com vitórias e cobertura',
    query: `SELECT language, tier, toolchain, lib,
       round(exp(avg(ln(rel_time))), 2) AS score,
       count(*) FILTER (rel_time <= 1.01) AS wins,
       count(*)                         AS coverage
FROM results
GROUP BY ALL
ORDER BY score
LIMIT 5;`
  },
  {
    id: 'best_per_op',
    name: 'Melhor implementação por operação',
    query: `SELECT op, language, tier, toolchain, lib,
       round(exp(avg(ln(rel_time))), 2) AS score
FROM results
GROUP BY ALL
ORDER BY op, score;`
  },
  {
    id: 'tier_gain',
    name: 'Ganho de tier dentro da linguagem',
    query: `SELECT language, tier,
       round(exp(avg(ln(rel_time))), 2) AS score,
       count(*) AS tasks
FROM results
GROUP BY ALL
ORDER BY language, score;`
  },
  {
    id: 'gaps',
    name: 'Lacunas de suporte por formato',
    query: `SELECT format, op, mode,
       count(DISTINCT impl_id) AS supported_impls
FROM results
GROUP BY ALL
ORDER BY supported_impls ASC
LIMIT 6;`
  }
];

export default function SqlConsoleSection() {
  const { runCustomQuery, isDbReady } = useData();

  const [activePresetId, setActivePresetId] = useState<string>('ranking');
  const [query, setQuery] = useState<string>(presets[0].query);
  const [results, setResults] = useState<any[]>([]);
  const [latencyMs, setLatencyMs] = useState<number>(3.1);
  const [error, setError] = useState<string | null>(null);
  const [executing, setExecuting] = useState(false);

  const executeSql = async (sqlToRun: string) => {
    if (!isDbReady) return;
    setExecuting(true);
    setError(null);
    try {
      const { rows, latencyMs: lat } = await runCustomQuery(sqlToRun);
      setResults(rows);
      setLatencyMs(lat);
    } catch (err: any) {
      console.error('Erro na query SQL:', err);
      setError(err?.message || 'Erro ao executar consulta SQL');
    } finally {
      setExecuting(false);
    }
  };

  // Run initial query when DuckDB is ready
  useEffect(() => {
    if (isDbReady) {
      executeSql(query);
    }
  }, [isDbReady]);

  const selectPreset = (p: Preset) => {
    setActivePresetId(p.id);
    setQuery(p.query);
    executeSql(p.query);
  };

  // Keyboard shortcut: Cmd+Enter / Ctrl+Enter to execute
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      executeSql(query);
    }
  };

  const columns = results.length > 0 ? Object.keys(results[0]) : [];

  return (
    <section id="sql" className="mb-10 scroll-mt-28">
      
      <div className="bg-[var(--arena-surface)] border border-[var(--arena-border)] rounded-xl p-4 sm:p-5 shadow-sm">
        
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-[#C9501C] dark:text-[#E0703A] uppercase tracking-wider">
                Seção 06
              </span>
              <h2 className="text-xl font-bold tracking-tight text-[var(--arena-text-primary)]">
                Console SQL Interativo (DuckDB-Wasm)
              </h2>
            </div>
            <p className="text-xs text-[var(--arena-text-secondary)] mt-1">
              Consulte diretamente a tabela <code className="text-[#2E8B3E] dark:text-[#3DD68C] font-mono">results</code> usando SQL analítico in-browser.
            </p>
          </div>

          <div className="flex items-center gap-2 text-[11px] font-mono text-[var(--arena-text-muted)]">
            <Database className="w-3.5 h-3.5 text-[#2E8B3E] dark:text-[#3DD68C]" />
            <span>Motor analítico compilado em WebAssembly</span>
          </div>
        </div>

        {/* Horizontal Query Preset Chips on Top */}
        <div className="flex flex-wrap items-center gap-2 mb-4 pb-3 border-b border-[var(--arena-border)]/60">
          <span className="text-[11px] font-mono text-[var(--arena-text-muted)] mr-1">
            Consultas salvas:
          </span>
          {presets.map(p => {
            const active = activePresetId === p.id;
            return (
              <button
                key={p.id}
                onClick={() => selectPreset(p)}
                className={`px-3 py-1.5 rounded-lg text-xs font-mono transition-all cursor-pointer ${
                  active
                    ? 'bg-[var(--arena-canvas)] border border-[var(--arena-border-strong)] text-[var(--arena-text-primary)] font-bold shadow-xs'
                    : 'bg-transparent border border-[var(--arena-border)] text-[var(--arena-text-secondary)] hover:text-[var(--arena-text-primary)] hover:bg-[var(--arena-canvas)]'
                }`}
              >
                {p.name}
              </button>
            );
          })}
        </div>

        {/* Editor + Execution Bar (Full Width) */}
        <div className="space-y-4">
          
          <div className="bg-[var(--arena-canvas)] border border-[var(--arena-border)] rounded-lg overflow-hidden shadow-inner">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={5}
              className="w-full p-3 font-mono text-xs text-[var(--arena-text-primary)] bg-transparent resize-y focus:outline-none leading-relaxed"
              placeholder="Digite sua query SQL aqui..."
            />

            {/* Execution bar */}
            <div className="flex items-center justify-between px-3 py-2 bg-[var(--arena-surface)] border-t border-[var(--arena-border)] text-xs">
              <span className="font-mono text-[var(--arena-text-secondary)] text-[11px]">
                {results.length} linhas retornadas · {latencyMs.toFixed(1)} ms · DuckDB-Wasm
              </span>

              <button
                onClick={() => executeSql(query)}
                disabled={executing || !isDbReady}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-[#2E8B3E] hover:bg-[#256e31] dark:bg-[#3DD68C] dark:hover:bg-[#2fb875] text-white dark:text-black font-semibold text-xs transition-colors cursor-pointer disabled:opacity-50 shadow-xs"
              >
                <Play className="w-3 h-3 fill-current" />
                <span>Executar ⌘↵</span>
              </button>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-3 rounded-lg bg-[#C9501C]/10 border border-[#C9501C]/30 text-[#C9501C] dark:text-[#F2546B] text-xs font-mono">
              {error}
            </div>
          )}

          {/* Results Table */}
          {results.length > 0 && !error && (
            <div className="border border-[var(--arena-border)] rounded-lg overflow-x-auto bg-[var(--arena-canvas)]">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-[var(--arena-border)] bg-[var(--arena-surface)] text-[11px] font-mono text-[var(--arena-text-muted)]">
                    {columns.map(col => (
                      <th key={col} className="py-2 px-3 font-semibold capitalize">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {results.map((row, idx) => (
                    <tr key={idx} className="border-b border-[var(--arena-border)]/40 hover:bg-[var(--arena-raised)]/40 font-mono transition-colors">
                      {columns.map(col => {
                        const val = row[col];
                        const isScore = col === 'score' || col === 'rel_time';
                        const displayVal = typeof val === 'number' 
                          ? isScore ? val.toFixed(2).replace('.', ',') : val 
                          : String(val ?? '-');

                        return (
                          <td key={col} className="py-1.5 px-3 text-[var(--arena-text-primary)]">
                            {displayVal}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

        </div>

      </div>

    </section>
  );
}
