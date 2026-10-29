'use client';

import React from 'react';
import { Trophy, Zap, Gauge, Award, CheckCircle2 } from 'lucide-react';
import { useData } from '../context/DataContext';

export default function KpiCards() {
  const { metadata, tasks, allTasks } = useData();

  const totalFiltered = tasks.length;
  const totalOriginal = allTasks.length;

  const rustWinsFiltered = tasks.filter(t => t.winner === 'Rust').length;
  const goWinsFiltered = tasks.filter(t => t.winner === 'Go').length;
  const tiesFiltered = tasks.filter(t => t.winner === 'Empate' || t.winner === 'Tie').length;

  const rustPct = totalFiltered ? Math.round((rustWinsFiltered / totalFiltered) * 100) : 0;
  const goPct = totalFiltered ? Math.round((goWinsFiltered / totalFiltered) * 100) : 0;
  const tiesPct = totalFiltered ? Math.round((tiesFiltered / totalFiltered) * 100) : 0;

  // Throughput médio
  const avgGoThroughput = totalFiltered
    ? (tasks.reduce((acc, t) => acc + (t.go_throughput_mp_s || 0), 0) / totalFiltered).toFixed(1)
    : '0';
  const avgRustThroughput = totalFiltered
    ? (tasks.reduce((acc, t) => acc + (t.rust_throughput_mp_s || 0), 0) / totalFiltered).toFixed(1)
    : '0';

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 my-6">
      
      {/* Card 1: Razão Geométrica Global */}
      <div className="p-5 rounded-2xl bg-gradient-to-b from-slate-900 to-slate-950 border border-slate-800 relative overflow-hidden group hover:border-amber-500/50 transition-all">
        <div className="absolute top-0 right-0 w-28 h-28 bg-amber-500/10 rounded-full blur-2xl pointer-events-none" />
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Razão Geométrica</span>
          <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400">
            <Trophy className="w-5 h-5" />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-extrabold text-amber-400 tracking-tight">2.67x</span>
          <span className="text-xs text-slate-300 font-medium">Rust mais rápido</span>
        </div>
        <p className="mt-2 text-xs text-slate-400">
          Média geométrica global sobre o tempo de codec nos servidores.
        </p>
      </div>

      {/* Card 2: Vitórias Rust */}
      <div className="p-5 rounded-2xl bg-gradient-to-b from-slate-900 to-slate-950 border border-slate-800 relative overflow-hidden group hover:border-orange-500/50 transition-all">
        <div className="absolute top-0 right-0 w-28 h-28 bg-orange-500/10 rounded-full blur-2xl pointer-events-none" />
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Vitórias Rust</span>
          <div className="p-2 rounded-lg bg-orange-500/10 text-orange-400">
            <Zap className="w-5 h-5" />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-extrabold text-orange-400 tracking-tight">{rustWinsFiltered}</span>
          <span className="text-xs text-slate-400 font-medium">/ {totalFiltered} ({rustPct}%)</span>
        </div>
        <div className="w-full bg-slate-800 rounded-full h-1.5 mt-3 overflow-hidden">
          <div 
            className="bg-orange-500 h-1.5 rounded-full transition-all duration-500"
            style={{ width: `${rustPct}%` }}
          />
        </div>
      </div>

      {/* Card 3: Vitórias Go */}
      <div className="p-5 rounded-2xl bg-gradient-to-b from-slate-900 to-slate-950 border border-slate-800 relative overflow-hidden group hover:border-cyan-500/50 transition-all">
        <div className="absolute top-0 right-0 w-28 h-28 bg-cyan-500/10 rounded-full blur-2xl pointer-events-none" />
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Vitórias Go</span>
          <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
            <Award className="w-5 h-5" />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-extrabold text-cyan-400 tracking-tight">{goWinsFiltered}</span>
          <span className="text-xs text-slate-400 font-medium">/ {totalFiltered} ({goPct}%)</span>
        </div>
        <div className="w-full bg-slate-800 rounded-full h-1.5 mt-3 overflow-hidden">
          <div 
            className="bg-cyan-500 h-1.5 rounded-full transition-all duration-500"
            style={{ width: `${goPct}%` }}
          />
        </div>
      </div>

      {/* Card 4: Throughput Médio (MP/s) */}
      <div className="p-5 rounded-2xl bg-gradient-to-b from-slate-900 to-slate-950 border border-slate-800 relative overflow-hidden group hover:border-emerald-500/50 transition-all">
        <div className="absolute top-0 right-0 w-28 h-28 bg-emerald-500/10 rounded-full blur-2xl pointer-events-none" />
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Throughput Médio</span>
          <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
            <Gauge className="w-5 h-5" />
          </div>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-semibold text-cyan-400">Go: {avgGoThroughput}</span>
          <span className="text-xs text-slate-500">vs</span>
          <span className="text-sm font-semibold text-orange-400">Rust: {avgRustThroughput}</span>
          <span className="text-xs text-slate-400">MP/s</span>
        </div>
        <p className="mt-2 text-xs text-slate-400">
          {totalFiltered === totalOriginal
            ? `Todas as ${totalOriginal} tarefas ativas`
            : `Filtro ativo: ${totalFiltered} de ${totalOriginal} tarefas`}
        </p>
      </div>

    </div>
  );
}
