'use client';

import React, { useRef, useEffect } from 'react';
import { Search, RotateCcw, ChevronDown, Check } from 'lucide-react';
import { useData } from '../context/DataContext';

export default function FilterToolbar() {
  const { 
    filters, 
    updateFilter, 
    resetFilters, 
    filteredResults, 
    implementations,
    activeSql,
    queryLatencyMs 
  } = useData();

  const searchInputRef = useRef<HTMLInputElement>(null);

  // Focus search input on pressing '/'
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === '/' && document.activeElement !== searchInputRef.current) {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const uniqueTasksCount = new Set(filteredResults.map(r => r.task_id)).size;
  const uniqueImplsCount = new Set(filteredResults.map(r => r.impl_id)).size;

  const scrollToDuel = () => {
    const el = document.getElementById('duel-section');
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  };

  const ops = [
    { id: 'all', label: 'Todas' },
    { id: 'analyze', label: 'Analyze' },
    { id: 'encode', label: 'Encode' },
    { id: 'decode', label: 'Decode' },
    { id: 'transcode', label: 'Transcode' },
  ];

  return (
    <div className="sticky top-16 z-40 w-full mb-6">
      <div className="bg-[#111418] border border-[#222831] rounded-xl shadow-2xl p-3 sm:p-4 space-y-3">
        
        {/* Linha 1: Identity Filters */}
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          
          {/* Search Input */}
          <div className="relative flex-1 min-w-[200px] max-w-xs">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#6b7480]" />
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Buscar tarefa…"
              value={filters.search}
              onChange={(e) => updateFilter('search', e.target.value)}
              className="w-full h-8 pl-8 pr-7 text-xs bg-[#0d1013] border border-[#222831] rounded-md text-[#eceff3] placeholder-[#6b7480] focus:outline-none focus:border-[#2e3540] transition-colors"
            />
            <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-mono text-[#6b7480] px-1 py-0.5 border border-[#222831] rounded bg-[#111418] pointer-events-none">
              /
            </span>
          </div>

          {/* Select: Linguagem */}
          <div className="relative">
            <select
              value={filters.language}
              onChange={(e) => updateFilter('language', e.target.value)}
              className="appearance-none h-8 pl-3 pr-8 text-xs bg-[#0d1013] border border-[#222831] hover:border-[#2e3540] rounded-md text-[#eceff3] cursor-pointer focus:outline-none"
            >
              <option value="all">Linguagem: Todas · 6</option>
              <option value="rust">Rust</option>
              <option value="zig">Zig</option>
              <option value="go">Go</option>
              <option value="swift">Swift</option>
              <option value="csharp">C#</option>
              <option value="java">Java</option>
            </select>
            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#6b7480] pointer-events-none" />
          </div>

          {/* Select: Tier */}
          <div className="relative">
            <select
              value={filters.tier}
              onChange={(e) => updateFilter('tier', e.target.value)}
              className="appearance-none h-8 pl-3 pr-8 text-xs bg-[#0d1013] border border-[#222831] hover:border-[#2e3540] rounded-md text-[#eceff3] cursor-pointer focus:outline-none"
            >
              <option value="all">Tier: Todos · 3</option>
              <option value="accelerated">accelerated</option>
              <option value="portable">portable</option>
              <option value="hybrid">hybrid</option>
            </select>
            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#6b7480] pointer-events-none" />
          </div>

          {/* Select: Toolchain */}
          <div className="relative hidden md:block">
            <select
              value={filters.toolchain}
              onChange={(e) => updateFilter('toolchain', e.target.value)}
              className="appearance-none h-8 pl-3 pr-8 text-xs bg-[#0d1013] border border-[#222831] hover:border-[#2e3540] rounded-md text-[#eceff3] cursor-pointer focus:outline-none"
            >
              <option value="all">Toolchain: Todos</option>
              <option value="stable 1.90">Rust stable 1.90</option>
              <option value="nightly">Rust nightly</option>
              <option value="0.15">Zig 0.15</option>
              <option value="1.25">Go 1.25</option>
              <option value=".NET 10">.NET 10</option>
              <option value="6.2">Swift 6.2</option>
              <option value="GraalVM">GraalVM</option>
            </select>
            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#6b7480] pointer-events-none" />
          </div>

          {/* Select: Biblioteca */}
          <div className="relative hidden lg:block">
            <select
              value={filters.lib}
              onChange={(e) => updateFilter('lib', e.target.value)}
              className="appearance-none h-8 pl-3 pr-8 text-xs bg-[#0d1013] border border-[#222831] hover:border-[#2e3540] rounded-md text-[#eceff3] cursor-pointer focus:outline-none"
            >
              <option value="all">Biblioteca: Todas</option>
              <option value="padrão">padrão</option>
              <option value="libvips">libvips</option>
              <option value="cgo · libwebp/turbo">cgo libwebp</option>
              <option value="image-rs">image-rs</option>
              <option value="PGO · padrão">PGO padrão</option>
              <option value="x/image">x/image</option>
              <option value="noasm · padrão">noasm</option>
              <option value="NativeAOT">NativeAOT</option>
            </select>
            <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#6b7480] pointer-events-none" />
          </div>

          {/* Counter and Clear */}
          <div className="ml-auto flex items-center gap-3">
            <span className="text-xs font-mono text-[#a3acb9]">
              <strong className="text-[#eceff3]">{uniqueImplsCount}</strong> impl. · <strong className="text-[#eceff3]">{uniqueTasksCount}</strong> tarefas
            </span>

            <button
              onClick={resetFilters}
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-[#a3acb9] hover:text-[#eceff3] bg-[#0d1013] hover:bg-[#171b21] border border-[#222831] rounded-md transition-colors cursor-pointer"
              title="Limpar todos os filtros"
            >
              <RotateCcw className="w-3 h-3" />
              <span>Limpar</span>
            </button>
          </div>

        </div>

        {/* Linha 2: Benchmark Filters */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-[#222831]/60">
          
          {/* Operação Segmented Tabs */}
          <div className="flex items-center p-0.5 bg-[#0d1013] border border-[#222831] rounded-lg">
            {ops.map((op) => {
              const active = filters.op === op.id;
              return (
                <button
                  key={op.id}
                  onClick={() => updateFilter('op', op.id)}
                  className={`px-3 py-1 text-xs font-medium rounded-md transition-all cursor-pointer ${
                    active
                      ? 'bg-[#171b21] border border-[#2e3540] text-[#eceff3] shadow-sm'
                      : 'text-[#6b7480] hover:text-[#a3acb9]'
                  }`}
                >
                  {op.label}
                </button>
              );
            })}
          </div>

          {/* Formato, Modo, Imagem dropdowns */}
          <div className="flex items-center gap-2">
            
            {/* Formato */}
            <div className="relative">
              <select
                value={filters.format}
                onChange={(e) => updateFilter('format', e.target.value)}
                className="appearance-none h-7 pl-2.5 pr-6 text-xs bg-[#0d1013] border border-[#222831] hover:border-[#2e3540] rounded-md text-[#eceff3] cursor-pointer focus:outline-none"
              >
                <option value="all">Formato: Todos</option>
                <option value="png">PNG</option>
                <option value="jpeg">JPEG</option>
                <option value="webp">WebP</option>
                <option value="avif">AVIF</option>
                <option value="jxl">JXL</option>
                <option value="pam">PAM</option>
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-[#6b7480] pointer-events-none" />
            </div>

            {/* Modo */}
            <div className="relative">
              <select
                value={filters.mode}
                onChange={(e) => updateFilter('mode', e.target.value)}
                className="appearance-none h-7 pl-2.5 pr-6 text-xs bg-[#0d1013] border border-[#222831] hover:border-[#2e3540] rounded-md text-[#eceff3] cursor-pointer focus:outline-none"
              >
                <option value="all">Modo: Todos</option>
                <option value="lossy">Lossy</option>
                <option value="lossless">Lossless</option>
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-[#6b7480] pointer-events-none" />
            </div>

            {/* Imagem */}
            <div className="relative hidden sm:block">
              <select
                value={filters.image}
                onChange={(e) => updateFilter('image', e.target.value)}
                className="appearance-none h-7 pl-2.5 pr-6 text-xs bg-[#0d1013] border border-[#222831] hover:border-[#2e3540] rounded-md text-[#eceff3] cursor-pointer focus:outline-none"
              >
                <option value="all">Imagem: Todas</option>
                <option value="photo">Photo</option>
                <option value="screenshot">Screenshot</option>
                <option value="illustration">Illustration</option>
                <option value="alpha">Alpha</option>
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-[#6b7480] pointer-events-none" />
            </div>

          </div>

          {/* Toggles & Duel action */}
          <div className="flex items-center gap-3">
            
            {/* Toggle: Agrupar por linguagem */}
            <label className="flex items-center gap-2 text-xs text-[#a3acb9] cursor-pointer select-none">
              <input
                type="checkbox"
                checked={filters.groupByLanguage}
                onChange={(e) => updateFilter('groupByLanguage', e.target.checked)}
                className="sr-only"
              />
              <div className={`w-8 h-4.5 rounded-full transition-colors relative ${
                filters.groupByLanguage ? 'bg-[#3dd68c]' : 'bg-[#222831]'
              }`}>
                <div className={`w-3.5 h-3.5 rounded-full bg-white transition-transform absolute top-0.5 ${
                  filters.groupByLanguage ? 'translate-x-4' : 'translate-x-0.5'
                }`} />
              </div>
              <span className="hidden sm:inline">Agrupar por linguagem</span>
            </label>

            {/* Comparar 2 button */}
            <button
              onClick={scrollToDuel}
              className="px-3 py-1 rounded-full bg-[#171b21] hover:bg-[#222831] border border-[#2e3540] text-xs font-medium text-[#eceff3] transition-colors cursor-pointer"
            >
              Comparar 2
            </button>

          </div>

        </div>

        {/* Linha 3: SQL Ativo */}
        <div className="flex items-center justify-between gap-2 px-3 py-1.5 rounded-lg bg-[#0d1013] border border-[#222831] text-[11px] font-mono">
          <div className="flex items-center gap-2 overflow-hidden truncate">
            <span className="text-[#3dd68c] font-semibold shrink-0">SQL ATIVO</span>
            <span className="text-[#a3acb9] truncate">{activeSql}</span>
          </div>
          <span className="text-[#6b7480] shrink-0">
            DuckDB-Wasm · {queryLatencyMs.toFixed(1)} ms
          </span>
        </div>

      </div>
    </div>
  );
}
