'use client';

import React, { useState, useEffect } from 'react';
import { Terminal, Play, Check } from 'lucide-react';
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
       exp(avg(ln(rel_time)))           AS score,
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
       exp(avg(ln(rel_time))) AS score
FROM results
GROUP BY ALL
ORDER BY op, score;`
  },
  {
    id: 'tier_gain',
    name: 'Ganho de tier dentro da linguagem',
    query: `SELECT language, tier,
       exp(avg(ln(rel_time))) AS score,
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
  const [latencyMs, setLatencyMs] = useState<number>(4.2);
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
    <div id="sql-console" className="bg-[#111418] border border-[#222831] rounded-xl p-4 sm:p-5 mb-6 shadow-sm">
      
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        
        {/* Left: Presets Sidebar */}
        <div className="lg:col-span-1 border-b lg:border-b-0 lg:border-r border-[#222831] pb-4 lg:pb-0 lg:pr-4">
          <div className="flex items-center gap-2 mb-4">
            <Terminal className="w-4 h-4 text-[#3dd68c]" />
            <h3 className="text-sm font-semibold text-[#eceff3]">
              Console SQL
            </h3>
          </div>

          <div className="space-y-1.5">
            {presets.map(p => {
              const active = activePresetId === p.id;
              return (
                <button
                  key={p.id}
                  onClick={() => selectPreset(p)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors cursor-pointer ${
                    active
                      ? 'bg-[#171b21] border border-[#2e3540] text-[#eceff3] font-medium'
                      : 'text-[#a3acb9] hover:bg-[#171b21]/50 hover:text-[#eceff3]'
                  }`}
                >
                  {p.name}
                </button>
              );
            })}
          </div>

          <p className="mt-4 text-[11px] text-[#6b7480] leading-relaxed">
            Consulte a tabela <code className="text-[#3dd68c]">results</code> diretamente usando SQL padrão do DuckDB-Wasm compilado no seu navegador.
          </p>
        </div>

        {/* Right: Editor + Results */}
        <div className="lg:col-span-3 flex flex-col space-y-4">
          
          {/* Editor Container */}
          <div className="bg-[#0d1013] border border-[#222831] rounded-lg overflow-hidden">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={6}
              className="w-full p-3 font-mono text-xs text-[#eceff3] bg-transparent resize-y focus:outline-none leading-relaxed"
              placeholder="Digite sua query SQL aqui..."
            />

            {/* Execution bar */}
            <div className="flex items-center justify-between px-3 py-2 bg-[#111418] border-t border-[#222831] text-xs">
              <span className="font-mono text-[#6b7480] text-[11px]">
                {results.length} linhas · {latencyMs.toFixed(1)} ms · DuckDB-Wasm
              </span>

              <button
                onClick={() => executeSql(query)}
                disabled={executing || !isDbReady}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#3dd68c] hover:bg-[#2a9f6b] text-black font-semibold text-xs transition-colors cursor-pointer disabled:opacity-50"
              >
                <Play className="w-3 h-3 fill-current" />
                <span>Executar ⌘↵</span>
              </button>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-3 rounded-lg bg-[#5c2532]/30 border border-[#f2546b]/40 text-[#f2546b] text-xs font-mono">
              {error}
            </div>
          )}

          {/* Results Table */}
          {results.length > 0 && !error && (
            <div className="border border-[#222831] rounded-lg overflow-x-auto bg-[#0d1013]">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-[#222831] bg-[#111418] text-[11px] font-mono text-[#6b7480]">
                    {columns.map(col => (
                      <th key={col} className="py-2 px-3 font-semibold capitalize">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {results.map((row, idx) => (
                    <tr key={idx} className="border-b border-[#222831]/40 hover:bg-[#171b21]/50 font-mono">
                      {columns.map(col => {
                        const val = row[col];
                        const isScore = col === 'score' || col === 'rel_time';
                        const displayVal = typeof val === 'number' 
                          ? isScore ? val.toFixed(2).replace('.', ',') : val 
                          : String(val ?? '-');

                        return (
                          <td key={col} className="py-1.5 px-3 text-[#eceff3]">
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

    </div>
  );
}
