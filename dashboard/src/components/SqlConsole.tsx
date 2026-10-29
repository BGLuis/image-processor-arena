'use client';

import React, { useState } from 'react';
import { Terminal, Play, CheckCircle, AlertCircle, Sparkles } from 'lucide-react';
import { useData } from '../context/DataContext';

const SAMPLE_QUERIES = [
  {
    name: 'Top 5 Maiores Speedups do Rust',
    sql: "SELECT task, op, format, speedup, rust_throughput_mp_s, go_throughput_mp_s FROM benchmark_results WHERE winner = 'Rust' ORDER BY speedup DESC LIMIT 5;",
  },
  {
    name: 'Vitórias e Speedup Médio por Operação',
    sql: "SELECT op, COUNT(*) as total, SUM(CASE WHEN winner = 'Rust' THEN 1 ELSE 0 END) as rust_wins, SUM(CASE WHEN winner = 'Go' THEN 1 ELSE 0 END) as go_wins, ROUND(AVG(speedup), 2) as avg_speedup FROM benchmark_results GROUP BY op;",
  },
  {
    name: 'Throughput Médio por Formato',
    sql: "SELECT format, ROUND(AVG(go_throughput_mp_s), 1) as avg_go_mp_s, ROUND(AVG(rust_throughput_mp_s), 1) as avg_rust_mp_s FROM benchmark_results GROUP BY format ORDER BY avg_rust_mp_s DESC;",
  },
  {
    name: 'Tamanho Total de Saída por Formato (KB)',
    sql: "SELECT format, ROUND(SUM(go_bytes)/1024, 1) as go_total_kb, ROUND(SUM(rust_bytes)/1024, 1) as rust_total_kb FROM benchmark_results WHERE go_bytes > 0 GROUP BY format;",
  },
];

export default function SqlConsole() {
  const { runCustomQuery, isDbReady } = useData();
  const [query, setQuery] = useState(SAMPLE_QUERIES[0].sql);
  const [result, setResult] = useState<any[] | null>(null);
  const [queryTimeMs, setQueryTimeMs] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const handleExecute = async () => {
    if (!query.trim()) return;
    setRunning(true);
    setError(null);

    const start = performance.now();
    try {
      const rows = await runCustomQuery(query);
      const elapsed = performance.now() - start;
      setResult(rows);
      setQueryTimeMs(Number(elapsed.toFixed(2)));
    } catch (err: any) {
      setError(err?.message || 'Erro ao executar consulta SQL');
      setResult(null);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 my-6 backdrop-blur-sm">
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <Terminal className="w-5 h-5 text-emerald-400" />
          <h2 className="text-base sm:text-lg font-bold text-white">DuckDB SQL Console (In-Browser OLAP)</h2>
        </div>
        <span className="text-xs font-mono text-emerald-400 bg-emerald-950/60 border border-emerald-800/80 px-2.5 py-1 rounded-lg">
          DuckDB-Wasm SQL Engine
        </span>
      </div>

      <p className="text-xs text-slate-400 mb-4">
        Execute consultas analíticas SQL reais sobre a tabela <code className="text-cyan-400">benchmark_results</code> diretamente no motor DuckDB WebAssembly do seu navegador.
      </p>

      {/* Exemplos Rápidos */}
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <span className="text-xs font-semibold text-slate-400 flex items-center gap-1">
          <Sparkles className="w-3.5 h-3.5 text-amber-400" /> Consultas de Exemplo:
        </span>
        {SAMPLE_QUERIES.map((item, idx) => (
          <button
            key={idx}
            onClick={() => setQuery(item.sql)}
            className="text-[11px] px-2.5 py-1 rounded-lg bg-slate-950 hover:bg-slate-800 text-slate-300 border border-slate-800 transition-colors"
          >
            {item.name}
          </button>
        ))}
      </div>

      {/* Editor SQL */}
      <div className="relative mb-3">
        <textarea
          rows={3}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Digite sua query SQL aqui (ex: SELECT * FROM benchmark_results LIMIT 10;)"
          className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs sm:text-sm font-mono text-emerald-300 focus:outline-none focus:border-emerald-500 transition-colors resize-y"
        />
        <div className="flex justify-between items-center mt-2">
          <span className="text-[11px] text-slate-500 font-mono">
            Tabela disponível: <code className="text-slate-400">benchmark_results</code>
          </span>
          <button
            onClick={handleExecute}
            disabled={running || !isDbReady}
            className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 text-white font-medium text-xs flex items-center gap-1.5 transition-colors shadow-lg shadow-emerald-950/40"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>{running ? 'Executando...' : 'Executar SQL'}</span>
          </button>
        </div>
      </div>

      {/* Mensagens de Erro */}
      {error && (
        <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-800/80 text-rose-300 text-xs font-mono flex items-start gap-2 mb-4">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Tabela de Resultados da Query */}
      {result !== null && (
        <div className="mt-4 pt-4 border-t border-slate-800/80">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
            <span className="flex items-center gap-1 text-emerald-400 font-mono">
              <CheckCircle className="w-3.5 h-3.5" /> {result.length} linha(s) retornada(s)
            </span>
            {queryTimeMs !== null && (
              <span className="font-mono text-slate-500">
                Tempo de execução: {queryTimeMs} ms
              </span>
            )}
          </div>

          {result.length === 0 ? (
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-center text-xs text-slate-500">
              A consulta não retornou linhas.
            </div>
          ) : (
            <div className="overflow-x-auto max-h-72 border border-slate-800 rounded-xl bg-slate-950">
              <table className="w-full text-left text-xs whitespace-nowrap font-mono">
                <thead className="bg-slate-900 text-slate-400 uppercase text-[11px] font-semibold sticky top-0 border-b border-slate-800">
                  <tr>
                    {Object.keys(result[0]).map((col) => (
                      <th key={col} className="py-2.5 px-3">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {result.map((row, rowIdx) => (
                    <tr key={rowIdx} className="hover:bg-slate-800/30 transition-colors">
                      {Object.keys(result[0]).map((col) => (
                        <td key={col} className="py-2 px-3 text-slate-300">
                          {typeof row[col] === 'number' ? (
                            Number.isInteger(row[col]) ? row[col] : row[col].toFixed(2)
                          ) : (
                            String(row[col] ?? '-')
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
