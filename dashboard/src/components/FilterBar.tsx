'use client';

import React, { useState } from 'react';
import { Filter, Search, RotateCcw, Terminal, ChevronDown, ChevronUp } from 'lucide-react';
import { useData } from '../context/DataContext';

export default function FilterBar() {
  const { filters, updateFilter, resetFilters, activeSql, metadata } = useData();
  const [showSql, setShowSql] = useState(false);

  const ops = metadata?.filters_options?.ops || ['analyze', 'encode', 'decode', 'transcode'];
  const formats = metadata?.filters_options?.formats || ['pam', 'png', 'jpeg', 'webp', 'avif', 'jxl'];
  const modes = metadata?.filters_options?.modes || ['lossy', 'lossless'];
  const images = metadata?.filters_options?.images || ['photo.pam', 'screenshot.pam', 'illustration.pam', 'alpha.pam'];

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 sm:p-5 backdrop-blur-sm my-6">
      <div className="flex flex-col gap-4">
        
        {/* Linha Superior: Título dos Filtros e Busca */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-200">
            <Filter className="w-4 h-4 text-cyan-400" />
            <span>Filtros Dinâmicos</span>
          </div>

          <div className="flex items-center gap-2">
            {/* Input de Busca */}
            <div className="relative flex-1 sm:w-64">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Buscar tarefa, formato..."
                value={filters.search}
                onChange={(e) => updateFilter('search', e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-1.5 text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
              />
            </div>

            {/* Reset */}
            <button
              onClick={resetFilters}
              title="Restaurar todos os filtros"
              className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors flex items-center gap-1 text-xs"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Reset</span>
            </button>
          </div>
        </div>

        {/* Linha de Seletores */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          
          {/* Operação */}
          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Operação</label>
            <select
              value={filters.op}
              onChange={(e) => updateFilter('op', e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="all">Todas as Operações</option>
              {ops.map(op => (
                <option key={op} value={op}>{op.toUpperCase()}</option>
              ))}
            </select>
          </div>

          {/* Formato */}
          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Formato</label>
            <select
              value={filters.format}
              onChange={(e) => updateFilter('format', e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="all">Todos os Formatos</option>
              {formats.map(fmt => (
                <option key={fmt} value={fmt}>{fmt.toUpperCase()}</option>
              ))}
            </select>
          </div>

          {/* Modo */}
          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Modo</label>
            <select
              value={filters.mode}
              onChange={(e) => updateFilter('mode', e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="all">Todos os Modos</option>
              {modes.map(m => (
                <option key={m} value={m}>{m === 'lossy' ? 'Lossy (Com perda)' : 'Lossless (Sem perda)'}</option>
              ))}
            </select>
          </div>

          {/* Imagem */}
          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Imagem</label>
            <select
              value={filters.image}
              onChange={(e) => updateFilter('image', e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="all">Todas as Imagens</option>
              {images.map(img => (
                <option key={img} value={img}>{img}</option>
              ))}
            </select>
          </div>

          {/* Vencedor */}
          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Vencedor</label>
            <select
              value={filters.winner}
              onChange={(e) => updateFilter('winner', e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="all">Todos os Resultados</option>
              <option value="Rust">Rust Puro</option>
              <option value="Go">Go Puro</option>
              <option value="Empate">Empate Estatístico</option>
            </select>
          </div>

        </div>

        {/* Barra de Consulta SQL Ativa (DuckDB Inspector) */}
        <div className="pt-2 border-t border-slate-800/80">
          <div className="flex items-center justify-between">
            <button
              onClick={() => setShowSql(!showSql)}
              className="flex items-center gap-1.5 text-xs font-mono text-cyan-400 hover:text-cyan-300 transition-colors"
            >
              <Terminal className="w-3.5 h-3.5" />
              <span>DuckDB SQL Ativo</span>
              {showSql ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
            <span className="text-[11px] text-slate-500 font-mono">
              Executado via DuckDB-Wasm in-browser
            </span>
          </div>

          {showSql && (
            <div className="mt-2 p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-emerald-400 overflow-x-auto">
              <code>{activeSql}</code>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
