'use client';

import React, { useRef, useEffect, useState } from 'react';
import { Search, RotateCcw, ChevronDown, Check, Shield, Layers, SlidersHorizontal, X } from 'lucide-react';
import { useData } from '../context/DataContext';

const langConfig: Record<string, { label: string; color: string; count: number }> = {
  rust: { label: 'Rust', color: 'var(--lang-rust)', count: 1 },
  go: { label: 'Go', color: 'var(--lang-go)', count: 1 },
};

export default function FilterToolbar() {
  const { 
    filters, 
    updateFilter, 
    toggleLanguageFilter,
    setOnlyLanguage,
    resetFilters, 
    filteredResults, 
    activeSql,
    queryLatencyMs 
  } = useData();

  const searchInputRef = useRef<HTMLInputElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const [isLangPopoverOpen, setIsLangPopoverOpen] = useState(false);
  const [langSearch, setLangSearch] = useState('');

  // Close desktop popover on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setIsLangPopoverOpen(false);
      }
    };
    if (isLangPopoverOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
    }
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [isLangPopoverOpen]);

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
    const el = document.getElementById('duel');
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
    <div className="sticky top-16 z-40 w-full mb-8">
      <div className="bg-[var(--arena-surface)] border border-[var(--arena-border)] rounded-xl shadow-lg p-3 sm:p-4 space-y-3 transition-colors backdrop-blur-md">
        
        {/* Linha 1: Busca rápida, Contadores e Reset */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          
          {/* Search Input */}
          <div className="relative flex-1 min-w-[220px] max-w-sm">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--arena-text-muted)]" />
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Buscar tarefa por nome, formato ou imagem…"
              value={filters.search}
              onChange={(e) => updateFilter('search', e.target.value)}
              className="w-full h-8 pl-8 pr-7 text-xs bg-[var(--arena-canvas)] border border-[var(--arena-border)] rounded-lg text-[var(--arena-text-primary)] placeholder-[var(--arena-text-muted)] focus:outline-none focus:border-[var(--arena-border-strong)] transition-colors"
            />
            <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-mono text-[var(--arena-text-muted)] px-1 py-0.2 border border-[var(--arena-border)] rounded bg-[var(--arena-surface)] pointer-events-none">
              /
            </span>
          </div>

          {/* Counts & Clear */}
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono text-[var(--arena-text-secondary)]">
              <strong className="text-[var(--arena-text-primary)]">{uniqueImplsCount}</strong> impl. · <strong className="text-[var(--arena-text-primary)]">{uniqueTasksCount}</strong> tarefas
            </span>

            <button
              onClick={resetFilters}
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-[var(--arena-text-secondary)] hover:text-[var(--arena-text-primary)] bg-[var(--arena-canvas)] hover:bg-[var(--arena-raised)] border border-[var(--arena-border)] rounded-md transition-colors cursor-pointer"
              title="Limpar todos os filtros"
            >
              <RotateCcw className="w-3 h-3" />
              <span>Limpar</span>
            </button>
          </div>

        </div>

        {/* Linha 2: Pílulas de Linguagens (Go e Rust com "somente" no hover) e Arquitetura Zero FFI */}
        <div className="flex flex-wrap items-center justify-between gap-2.5 pt-2 border-t border-[var(--arena-border)]/60">
          
          {/* Language Pills + Popover trigger */}
          <div className="flex flex-wrap items-center gap-1.5 relative" ref={popoverRef}>
            <span className="text-[11px] font-mono text-[var(--arena-text-muted)] mr-1 hidden sm:inline">
              Linguagens:
            </span>

            {/* Quick Popover Trigger Button */}
            <button
              onClick={() => setIsLangPopoverOpen(prev => !prev)}
              className={`flex items-center gap-1.5 px-2.5 h-7 rounded-md border text-xs font-mono transition-colors cursor-pointer ${
                isLangPopoverOpen || filters.selectedLanguages.length > 0
                  ? 'bg-[var(--arena-canvas)] border-[var(--arena-border-strong)] text-[var(--arena-text-primary)] font-semibold shadow-xs'
                  : 'bg-transparent border-[var(--arena-border)] text-[var(--arena-text-secondary)] hover:text-[var(--arena-text-primary)] hover:bg-[var(--arena-canvas)]'
              }`}
              title="Abrir popover com busca e checkboxes de linguagens"
            >
              <SlidersHorizontal className="w-3 h-3 text-[#C9501C] dark:text-[#E0703A]" />
              <span className="hidden sm:inline">Filtrar...</span>
              <span className="sm:hidden">Linguagens</span>
              {filters.selectedLanguages.length > 0 && (
                <span className="w-4 h-4 rounded-full bg-[#C9501C] dark:bg-[#E0703A] text-white text-[9px] flex items-center justify-center font-bold">
                  {filters.selectedLanguages.length}
                </span>
              )}
              <ChevronDown className={`w-3 h-3 transition-transform ${isLangPopoverOpen ? 'rotate-180' : ''}`} />
            </button>

            {/* Desktop Popover Menu */}
            {isLangPopoverOpen && (
              <div className="hidden sm:block absolute left-0 top-full mt-2 w-80 rounded-xl bg-[var(--arena-surface)] border border-[var(--arena-border-strong)] shadow-2xl p-3.5 z-50 animate-in fade-in zoom-in-95 duration-150">
                <div className="flex items-center justify-between pb-2 border-b border-[var(--arena-border)]/60">
                  <div className="flex items-center gap-1.5">
                    <SlidersHorizontal className="w-3.5 h-3.5 text-[#C9501C] dark:text-[#E0703A]" />
                    <span className="text-xs font-bold text-[var(--arena-text-primary)]">
                      Filtrar Linguagens
                    </span>
                  </div>
                  <button
                    onClick={() => setIsLangPopoverOpen(false)}
                    className="p-1 rounded text-[var(--arena-text-muted)] hover:text-[var(--arena-text-primary)] cursor-pointer"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* Internal Search Input */}
                <div className="relative my-2.5">
                  <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--arena-text-muted)]" />
                  <input
                    type="text"
                    placeholder="Filtrar linguagens..."
                    value={langSearch}
                    onChange={(e) => setLangSearch(e.target.value)}
                    className="w-full h-7 pl-7 pr-2.5 text-xs bg-[var(--arena-canvas)] border border-[var(--arena-border)] rounded-md text-[var(--arena-text-primary)] placeholder-[var(--arena-text-muted)] focus:outline-none focus:border-[var(--arena-border-strong)]"
                  />
                </div>

                {/* Checkboxes List with 'somente' action */}
                <div className="space-y-1 max-h-48 overflow-y-auto my-2 pr-1">
                  {Object.entries(langConfig)
                    .filter(([_, info]) => info.label.toLowerCase().includes(langSearch.toLowerCase()))
                    .map(([langKey, info]) => {
                      const isChecked = filters.selectedLanguages.length === 0 || filters.selectedLanguages.includes(langKey);
                      return (
                        <div key={langKey} className="group/item flex items-center justify-between p-1.5 rounded-lg hover:bg-[var(--arena-canvas)] transition-colors">
                          <label className="flex items-center gap-2 text-xs font-medium text-[var(--arena-text-primary)] cursor-pointer flex-1">
                            <input
                              type="checkbox"
                              checked={filters.selectedLanguages.includes(langKey)}
                              onChange={() => toggleLanguageFilter(langKey)}
                              className="rounded border-[var(--arena-border)] text-[#C9501C] focus:ring-0 cursor-pointer"
                            />
                            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: info.color }} />
                            <span>{info.label}</span>
                            <span className="text-[10px] font-mono text-[var(--arena-text-muted)]">({info.count} impl)</span>
                          </label>
                          <button
                            onClick={() => {
                              setOnlyLanguage(langKey);
                              setIsLangPopoverOpen(false);
                            }}
                            className="text-[10px] font-mono px-2 py-0.5 rounded bg-[var(--arena-canvas)] hover:bg-[var(--arena-raised)] border border-[var(--arena-border)] text-[var(--arena-text-muted)] hover:text-[var(--arena-text-primary)] opacity-0 group-hover/item:opacity-100 transition-opacity cursor-pointer"
                            title={`Ver somente ${info.label}`}
                          >
                            somente
                          </button>
                        </div>
                      );
                    })}
                </div>

                {/* Popover Footer Shortcuts */}
                <div className="flex items-center justify-between pt-2 border-t border-[var(--arena-border)]/60 text-[11px] font-mono">
                  <button
                    onClick={() => updateFilter('selectedLanguages', [])}
                    className="text-[var(--arena-text-muted)] hover:text-[var(--arena-text-primary)] cursor-pointer"
                  >
                    Selecionar todas
                  </button>
                  <button
                    onClick={() => updateFilter('selectedLanguages', ['none'])}
                    className="text-[var(--arena-text-muted)] hover:text-[var(--arena-text-primary)] cursor-pointer"
                  >
                    Limpar seleção
                  </button>
                </div>
              </div>
            )}

            {/* Desktop Quick Pills */}
            <div className="hidden sm:flex items-center gap-1.5">
              {Object.entries(langConfig).map(([langKey, info]) => {
                const isSelected = filters.selectedLanguages.length === 0 || filters.selectedLanguages.includes(langKey);
                const isExclusivelySelected = filters.selectedLanguages.length === 1 && filters.selectedLanguages[0] === langKey;

                return (
                  <div
                    key={langKey}
                    className={`group relative flex items-center h-7 rounded-md border text-xs font-medium transition-all ${
                      isSelected
                        ? 'bg-[var(--arena-canvas)] border-[var(--arena-border-strong)] text-[var(--arena-text-primary)] shadow-xs'
                        : 'bg-transparent border-[var(--arena-border)]/50 text-[var(--arena-text-muted)] opacity-60 hover:opacity-100'
                    }`}
                  >
                    <button
                      onClick={() => toggleLanguageFilter(langKey)}
                      className="flex items-center gap-1.5 px-2 h-full cursor-pointer"
                      title={`Filtrar ${info.label}`}
                    >
                      <span 
                        className="w-2 h-2 rounded-full shrink-0" 
                        style={{ backgroundColor: info.color }} 
                      />
                      <span>{info.label}</span>
                      <span className="text-[10px] font-mono text-[var(--arena-text-muted)]">
                        {info.count}
                      </span>
                    </button>

                    {!isExclusivelySelected && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setOnlyLanguage(langKey);
                        }}
                        className="hidden group-hover:flex items-center px-1.5 h-full border-l border-[var(--arena-border)] text-[10px] font-mono text-[var(--arena-text-muted)] hover:text-[var(--arena-text-primary)] bg-[var(--arena-surface)] rounded-r-md cursor-pointer transition-colors"
                        title={`Ver somente ${info.label}`}
                      >
                        somente
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Arquitetura Zero FFI Badge */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[var(--arena-canvas)] border border-[var(--arena-border)] text-xs font-mono text-[var(--arena-text-secondary)]">
            <Shield className="w-3.5 h-3.5 text-[#2E8B3E] dark:text-[#3DD68C]" />
            <span className="font-medium text-[var(--arena-text-primary)]">Zero FFI</span>
            <span className="hidden md:inline text-[11px] text-[var(--arena-text-muted)]">· sem CGO / binários C</span>
          </div>

        </div>

        {/* Linha 3: Dimensões (Operação, Formato, Modo, Imagem), Agrupar e Link Duelo */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-[var(--arena-border)]/60">
          
          {/* Operation Tabs */}
          <div className="flex items-center p-0.5 bg-[var(--arena-canvas)] border border-[var(--arena-border)] rounded-lg">
            {ops.map((op) => {
              const active = filters.op === op.id;
              return (
                <button
                  key={op.id}
                  onClick={() => updateFilter('op', op.id)}
                  className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all cursor-pointer ${
                    active
                      ? 'bg-[var(--arena-surface)] text-[var(--arena-text-primary)] shadow-xs font-semibold'
                      : 'text-[var(--arena-text-muted)] hover:text-[var(--arena-text-secondary)]'
                  }`}
                >
                  {op.label}
                </button>
              );
            })}
          </div>

          {/* Formato, Modo, Imagem Dropdowns */}
          <div className="flex items-center gap-2">
            
            {/* Formato */}
            <div className="relative">
              <select
                value={filters.format}
                onChange={(e) => updateFilter('format', e.target.value)}
                className="appearance-none h-7 pl-2.5 pr-6 text-xs bg-[var(--arena-canvas)] border border-[var(--arena-border)] hover:border-[var(--arena-border-strong)] rounded-md text-[var(--arena-text-primary)] cursor-pointer focus:outline-none"
              >
                <option value="all">Formato: Todos</option>
                <option value="png">PNG</option>
                <option value="jpeg">JPEG</option>
                <option value="webp">WebP</option>
                <option value="avif">AVIF</option>
                <option value="jxl">JXL</option>
                <option value="pam">PAM</option>
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-[var(--arena-text-muted)] pointer-events-none" />
            </div>

            {/* Modo */}
            <div className="relative">
              <select
                value={filters.mode}
                onChange={(e) => updateFilter('mode', e.target.value)}
                className="appearance-none h-7 pl-2.5 pr-6 text-xs bg-[var(--arena-canvas)] border border-[var(--arena-border)] hover:border-[var(--arena-border-strong)] rounded-md text-[var(--arena-text-primary)] cursor-pointer focus:outline-none"
              >
                <option value="all">Modo: Todos</option>
                <option value="lossy">Lossy</option>
                <option value="lossless">Lossless</option>
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-[var(--arena-text-muted)] pointer-events-none" />
            </div>

            {/* Imagem */}
            <div className="relative hidden sm:block">
              <select
                value={filters.image}
                onChange={(e) => updateFilter('image', e.target.value)}
                className="appearance-none h-7 pl-2.5 pr-6 text-xs bg-[var(--arena-canvas)] border border-[var(--arena-border)] hover:border-[var(--arena-border-strong)] rounded-md text-[var(--arena-text-primary)] cursor-pointer focus:outline-none"
              >
                <option value="all">Imagem: Todas</option>
                <option value="photo">Photo</option>
                <option value="screenshot">Screenshot</option>
                <option value="illustration">Illustration</option>
                <option value="alpha">Alpha</option>
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-[var(--arena-text-muted)] pointer-events-none" />
            </div>

          </div>

          {/* Group Toggle & Duel shortcut */}
          <div className="flex items-center gap-3">
            
            <label className="flex items-center gap-2 text-xs text-[var(--arena-text-secondary)] cursor-pointer select-none">
              <input
                type="checkbox"
                checked={filters.groupByLanguage}
                onChange={(e) => updateFilter('groupByLanguage', e.target.checked)}
                className="sr-only"
              />
              <div className={`w-8 h-4.5 rounded-full transition-colors relative ${
                filters.groupByLanguage ? 'bg-[#2E8B3E] dark:bg-[#3DD68C]' : 'bg-[var(--arena-border)]'
              }`}>
                <div className={`w-3.5 h-3.5 rounded-full bg-white transition-transform absolute top-0.5 ${
                  filters.groupByLanguage ? 'translate-x-4' : 'translate-x-0.5'
                }`} />
              </div>
              <span className="hidden sm:inline">Agrupar</span>
            </label>

            <button
              onClick={scrollToDuel}
              className="px-2.5 py-1 rounded-md bg-[var(--arena-canvas)] hover:bg-[var(--arena-raised)] border border-[var(--arena-border)] text-xs font-mono font-medium text-[var(--arena-text-primary)] transition-colors cursor-pointer"
            >
              Ir ao Duelo →
            </button>

          </div>

        </div>

        {/* Linha de SQL Ativo */}
        <div className="flex items-center justify-between gap-2 px-3 py-1.5 rounded-lg bg-[var(--arena-canvas)] border border-[var(--arena-border)] text-[11px] font-mono">
          <div className="flex items-center gap-2 overflow-hidden truncate">
            <span className="text-[#2E8B3E] dark:text-[#3DD68C] font-semibold shrink-0">SQL ATIVO</span>
            <span className="text-[var(--arena-text-secondary)] truncate">{activeSql}</span>
          </div>
          <span className="text-[var(--arena-text-muted)] shrink-0">
            DuckDB-Wasm · {queryLatencyMs.toFixed(1)} ms
          </span>
        </div>

        {/* Mobile Bottom Sheet Drawer (screen < 640px) */}
        {isLangPopoverOpen && (
          <div className="sm:hidden fixed inset-0 z-50 flex flex-col justify-end">
            {/* Backdrop */}
            <div 
              className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity" 
              onClick={() => setIsLangPopoverOpen(false)} 
            />

            {/* Bottom Sheet Modal */}
            <div className="relative z-10 w-full max-h-[85vh] bg-[var(--arena-surface)] rounded-t-2xl border-t border-[var(--arena-border-strong)] shadow-2xl p-4 flex flex-col overflow-hidden animate-in slide-in-from-bottom duration-200">
              <div className="w-12 h-1 bg-[var(--arena-border-strong)] rounded-full mx-auto mb-3" />
              <div className="flex items-center justify-between pb-2 border-b border-[var(--arena-border)]/60">
                <div className="flex items-center gap-2">
                  <SlidersHorizontal className="w-4 h-4 text-[#C9501C] dark:text-[#E0703A]" />
                  <span className="text-sm font-bold text-[var(--arena-text-primary)]">
                    Filtrar Linguagens
                  </span>
                </div>
                <button
                  onClick={() => setIsLangPopoverOpen(false)}
                  className="p-1 rounded-lg text-[var(--arena-text-muted)] hover:text-[var(--arena-text-primary)] cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Internal search */}
              <div className="relative my-3">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--arena-text-muted)]" />
                <input
                  type="text"
                  placeholder="Buscar linguagem..."
                  value={langSearch}
                  onChange={(e) => setLangSearch(e.target.value)}
                  className="w-full h-8 pl-8 pr-3 text-xs bg-[var(--arena-canvas)] border border-[var(--arena-border)] rounded-lg text-[var(--arena-text-primary)] placeholder-[var(--arena-text-muted)] focus:outline-none"
                />
              </div>

              {/* Options list */}
              <div className="space-y-1.5 max-h-60 overflow-y-auto my-2 pr-1">
                {Object.entries(langConfig)
                  .filter(([_, info]) => info.label.toLowerCase().includes(langSearch.toLowerCase()))
                  .map(([langKey, info]) => {
                    const isChecked = filters.selectedLanguages.length === 0 || filters.selectedLanguages.includes(langKey);
                    return (
                      <div key={langKey} className="flex items-center justify-between p-2 rounded-lg bg-[var(--arena-canvas)] border border-[var(--arena-border)]">
                        <label className="flex items-center gap-2.5 text-xs font-medium text-[var(--arena-text-primary)] cursor-pointer flex-1">
                          <input
                            type="checkbox"
                            checked={filters.selectedLanguages.includes(langKey)}
                            onChange={() => toggleLanguageFilter(langKey)}
                            className="w-4 h-4 rounded border-[var(--arena-border)] text-[#C9501C] focus:ring-0 cursor-pointer"
                          />
                          <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: info.color }} />
                          <span>{info.label}</span>
                          <span className="text-[10px] font-mono text-[var(--arena-text-muted)]">({info.count} impl.)</span>
                        </label>
                        <button
                          onClick={() => {
                            setOnlyLanguage(langKey);
                            setIsLangPopoverOpen(false);
                          }}
                          className="text-[11px] font-mono px-2.5 py-1 rounded bg-[var(--arena-surface)] border border-[var(--arena-border)] text-[var(--arena-text-primary)] font-semibold cursor-pointer"
                        >
                          somente
                        </button>
                      </div>
                    );
                  })}
              </div>

              {/* Action buttons */}
              <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-[var(--arena-border)]/60">
                <button
                  onClick={() => updateFilter('selectedLanguages', [])}
                  className="py-2 text-xs font-mono font-medium rounded-lg bg-[var(--arena-canvas)] border border-[var(--arena-border)] text-[var(--arena-text-primary)] cursor-pointer"
                >
                  Todas (2)
                </button>
                <button
                  onClick={() => setIsLangPopoverOpen(false)}
                  className="py-2 text-xs font-mono font-bold rounded-lg bg-[#C9501C] dark:bg-[#E0703A] text-white cursor-pointer"
                >
                  Concluir
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
