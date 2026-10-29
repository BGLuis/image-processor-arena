'use client';

import React, { useState, useMemo } from 'react';
import { ArrowUpDown, ArrowUp, ArrowDown, ExternalLink } from 'lucide-react';
import { useData } from '../context/DataContext';
import type { BenchmarkTask } from '../types';

type SortField = 'id' | 'task' | 'op' | 'format' | 'go_codec_median_ms' | 'rust_codec_median_ms' | 'go_throughput_mp_s' | 'rust_throughput_mp_s' | 'go_bytes' | 'rust_bytes' | 'speedup';

export default function ResultsTable() {
  const { tasks } = useData();
  const [sortField, setSortField] = useState<SortField>('id');
  const [sortAsc, setSortAsc] = useState<boolean>(true);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  const sortedTasks = useMemo(() => {
    return [...tasks].sort((a, b) => {
      let valA: any = a[sortField];
      let valB: any = b[sortField];

      if (valA === null || valA === undefined) valA = 0;
      if (valB === null || valB === undefined) valB = 0;

      if (typeof valA === 'string') {
        valA = valA.toLowerCase();
        valB = (valB as string).toLowerCase();
      }

      if (valA < valB) return sortAsc ? -1 : 1;
      if (valA > valB) return sortAsc ? 1 : -1;
      return 0;
    });
  }, [tasks, sortField, sortAsc]);

  const renderSortIcon = (field: SortField) => {
    if (sortField !== field) {
      return <ArrowUpDown className="w-3 h-3 text-slate-500 inline ml-1 opacity-50" />;
    }
    return sortAsc 
      ? <ArrowUp className="w-3 h-3 text-cyan-400 inline ml-1" />
      : <ArrowDown className="w-3 h-3 text-cyan-400 inline ml-1" />;
  };

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 my-6 backdrop-blur-sm overflow-hidden">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
        <div>
          <h2 className="text-base sm:text-lg font-bold text-white">Tabela Analítica Completa</h2>
          <p className="text-xs text-slate-400">
            Exibindo {sortedTasks.length} de {tasks.length} tarefas. Clique nos cabeçalhos para ordenar.
          </p>
        </div>
      </div>

      <div className="overflow-x-auto -mx-5 px-5">
        <table className="w-full text-left text-xs whitespace-nowrap">
          <thead className="bg-slate-950/80 text-slate-400 uppercase text-[11px] font-semibold border-b border-slate-800">
            <tr>
              <th onClick={() => handleSort('task')} className="py-3 px-3 cursor-pointer hover:text-white">
                Tarefa {renderSortIcon('task')}
              </th>
              <th onClick={() => handleSort('op')} className="py-3 px-2 cursor-pointer hover:text-white">
                Operação {renderSortIcon('op')}
              </th>
              <th onClick={() => handleSort('format')} className="py-3 px-2 cursor-pointer hover:text-white">
                Formato {renderSortIcon('format')}
              </th>
              <th onClick={() => handleSort('go_codec_median_ms')} className="py-3 px-3 cursor-pointer hover:text-cyan-400 text-right">
                Go Codec (ms) {renderSortIcon('go_codec_median_ms')}
              </th>
              <th onClick={() => handleSort('go_throughput_mp_s')} className="py-3 px-3 cursor-pointer hover:text-cyan-400 text-right">
                Go MP/s {renderSortIcon('go_throughput_mp_s')}
              </th>
              <th onClick={() => handleSort('rust_codec_median_ms')} className="py-3 px-3 cursor-pointer hover:text-orange-400 text-right">
                Rust Codec (ms) {renderSortIcon('rust_codec_median_ms')}
              </th>
              <th onClick={() => handleSort('rust_throughput_mp_s')} className="py-3 px-3 cursor-pointer hover:text-orange-400 text-right">
                Rust MP/s {renderSortIcon('rust_throughput_mp_s')}
              </th>
              <th onClick={() => handleSort('go_bytes')} className="py-3 px-3 cursor-pointer hover:text-white text-right">
                Go (KB) {renderSortIcon('go_bytes')}
              </th>
              <th onClick={() => handleSort('rust_bytes')} className="py-3 px-3 cursor-pointer hover:text-white text-right">
                Rust (KB) {renderSortIcon('rust_bytes')}
              </th>
              <th className="py-3 px-3 text-center">
                Qualidade
              </th>
              <th onClick={() => handleSort('speedup')} className="py-3 px-3 cursor-pointer hover:text-white text-center">
                Vencedor {renderSortIcon('speedup')}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono">
            {sortedTasks.map((t) => {
              const isRustWinner = t.winner === 'Rust';
              const isGoWinner = t.winner === 'Go';
              const isTie = t.winner === 'Empate' || t.winner === 'Tie';

              return (
                <tr key={t.id} className="hover:bg-slate-800/40 transition-colors">
                  {/* Tarefa */}
                  <td className="py-2.5 px-3 font-sans font-medium text-slate-200">
                    {t.task}
                  </td>
                  {/* Operação */}
                  <td className="py-2.5 px-2 font-sans">
                    <span className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300 font-semibold uppercase">
                      {t.op}
                    </span>
                  </td>
                  {/* Formato */}
                  <td className="py-2.5 px-2 font-sans text-slate-300 uppercase text-[11px]">
                    {t.format}
                  </td>
                  {/* Go Codec */}
                  <td className="py-2.5 px-3 text-right text-cyan-300" title={`p25: ${t.go_codec_p25_ms}ms, p75: ${t.go_codec_p75_ms}ms`}>
                    {t.go_codec_median_ms ? t.go_codec_median_ms.toFixed(2) : '-'}
                  </td>
                  {/* Go Throughput */}
                  <td className="py-2.5 px-3 text-right text-cyan-400">
                    {t.go_throughput_mp_s ? t.go_throughput_mp_s.toFixed(1) : '-'}
                  </td>
                  {/* Rust Codec */}
                  <td className="py-2.5 px-3 text-right text-orange-300" title={`p25: ${t.rust_codec_p25_ms}ms, p75: ${t.rust_codec_p75_ms}ms`}>
                    {t.rust_codec_median_ms ? t.rust_codec_median_ms.toFixed(2) : '-'}
                  </td>
                  {/* Rust Throughput */}
                  <td className="py-2.5 px-3 text-right text-orange-400">
                    {t.rust_throughput_mp_s ? t.rust_throughput_mp_s.toFixed(1) : '-'}
                  </td>
                  {/* Go Bytes */}
                  <td className="py-2.5 px-3 text-right text-slate-300">
                    {t.go_bytes ? (t.go_bytes / 1024).toFixed(1) : '-'}
                  </td>
                  {/* Rust Bytes */}
                  <td className="py-2.5 px-3 text-right text-slate-300">
                    {t.rust_bytes ? (t.rust_bytes / 1024).toFixed(1) : '-'}
                  </td>
                  {/* Qualidade */}
                  <td className="py-2.5 px-3 text-center text-[11px]">
                    {t.go_exact && t.rust_exact ? (
                      <span className="text-emerald-400">exato</span>
                    ) : t.go_psnr_db ? (
                      <span className="text-slate-400">{t.go_psnr_db.toFixed(1)} dB</span>
                    ) : (
                      <span className="text-slate-600">-</span>
                    )}
                  </td>
                  {/* Vencedor */}
                  <td className="py-2.5 px-3 text-center">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold ${
                      isRustWinner 
                        ? 'bg-orange-950/80 text-orange-400 border border-orange-800' 
                        : isGoWinner 
                        ? 'bg-cyan-950/80 text-cyan-400 border border-cyan-800' 
                        : 'bg-purple-950/80 text-purple-400 border border-purple-800'
                    }`}>
                      {t.winner} {t.speedup ? `(${t.speedup.toFixed(2)}x)` : ''}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
