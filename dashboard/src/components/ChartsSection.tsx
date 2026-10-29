'use client';

import React, { useState } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, 
  CartesianGrid, Cell, PieChart, Pie 
} from 'recharts';
import { BarChart3, Clock, PieChart as PieIcon, HardDrive } from 'lucide-react';
import { useData } from '../context/DataContext';

export default function ChartsSection() {
  const { tasks, perOperation } = useData();
  const [activeTab, setActiveTab] = useState<'throughput' | 'latency' | 'operations' | 'bytes'>('throughput');

  if (!tasks.length) {
    return (
      <div className="p-8 text-center bg-slate-900/40 border border-slate-800 rounded-2xl text-slate-400">
        Nenhum dado encontrado para os filtros selecionados.
      </div>
    );
  }

  // Prepara dados de throughput
  const throughputData = tasks.map(t => ({
    name: t.task.replace(/\[.*?\]/, '').trim(),
    fullName: t.task,
    Go: t.go_throughput_mp_s ? Number(t.go_throughput_mp_s.toFixed(2)) : 0,
    Rust: t.rust_throughput_mp_s ? Number(t.rust_throughput_mp_s.toFixed(2)) : 0,
    winner: t.winner,
  }));

  // Prepara dados de latência
  const latencyData = tasks.map(t => ({
    name: t.task.replace(/\[.*?\]/, '').trim(),
    fullName: t.task,
    Go: t.go_codec_median_ms ? Number(t.go_codec_median_ms.toFixed(2)) : 0,
    Rust: t.rust_codec_median_ms ? Number(t.rust_codec_median_ms.toFixed(2)) : 0,
    winner: t.winner,
  }));

  // Prepara dados de bytes
  const bytesData = tasks
    .filter(t => t.go_bytes > 0 && t.rust_bytes > 0)
    .map(t => ({
      name: t.task.replace(/\[.*?\]/, '').trim(),
      fullName: t.task,
      GoKB: Number((t.go_bytes / 1024).toFixed(1)),
      RustKB: Number((t.rust_bytes / 1024).toFixed(1)),
      ratio: t.bytes_ratio ? Number(t.bytes_ratio.toFixed(2)) : 1,
    }));

  // Prepara dados de vitórias por operação
  const opData = perOperation.map(op => ({
    op: op.op.toUpperCase(),
    Go: op.go_wins,
    Rust: op.rust_wins,
    Empates: op.ties,
    geomean: op.geomean_go_over_rust ? Number(op.geomean_go_over_rust.toFixed(2)) : 1,
  }));

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 my-6 backdrop-blur-sm">
      
      {/* Tabs de Seleção de Gráficos */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-4 mb-5">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-cyan-400" />
          <h2 className="text-base sm:text-lg font-bold text-white">Visualizações Analíticas</h2>
        </div>

        <div className="flex flex-wrap items-center gap-1.5 p-1 bg-slate-950 rounded-xl border border-slate-800 text-xs">
          <button
            onClick={() => setActiveTab('throughput')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-colors flex items-center gap-1.5 ${
              activeTab === 'throughput' 
                ? 'bg-cyan-950 text-cyan-400 border border-cyan-800' 
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span>Throughput (MP/s)</span>
          </button>

          <button
            onClick={() => setActiveTab('latency')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-colors flex items-center gap-1.5 ${
              activeTab === 'latency' 
                ? 'bg-orange-950 text-orange-400 border border-orange-800' 
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            <span>Latência Codec (ms)</span>
          </button>

          <button
            onClick={() => setActiveTab('operations')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-colors flex items-center gap-1.5 ${
              activeTab === 'operations' 
                ? 'bg-amber-950 text-amber-400 border border-amber-800' 
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <PieIcon className="w-3.5 h-3.5" />
            <span>Vitórias por Operação</span>
          </button>

          <button
            onClick={() => setActiveTab('bytes')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-colors flex items-center gap-1.5 ${
              activeTab === 'bytes' 
                ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' 
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <HardDrive className="w-3.5 h-3.5" />
            <span>Tamanho Saída (KB)</span>
          </button>
        </div>
      </div>

      {/* Conteúdo do Gráfico */}
      <div className="h-80 sm:h-96 w-full">
        {activeTab === 'throughput' && (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={throughputData} margin={{ top: 10, right: 10, left: -20, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis 
                dataKey="name" 
                stroke="#64748b" 
                fontSize={11} 
                interval={0} 
                angle={-45} 
                textAnchor="end" 
              />
              <YAxis stroke="#64748b" fontSize={11} unit=" MP/s" />
              <Tooltip 
                contentStyle={{ backgroundColor: '#090d16', borderColor: '#334155', borderRadius: '0.75rem', fontSize: '12px' }}
                formatter={(val: any, name: any) => [`${val} MP/s`, name === 'Go' ? 'Go Puro' : 'Rust Puro']}
                labelFormatter={(label, payload) => payload?.[0]?.payload?.fullName || label}
              />
              <Legend verticalAlign="top" height={36} />
              <Bar dataKey="Go" fill="#06b6d4" radius={[4, 4, 0, 0]} name="Go Puro" />
              <Bar dataKey="Rust" fill="#f97316" radius={[4, 4, 0, 0]} name="Rust Puro" />
            </BarChart>
          </ResponsiveContainer>
        )}

        {activeTab === 'latency' && (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={latencyData} margin={{ top: 10, right: 10, left: -20, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis 
                dataKey="name" 
                stroke="#64748b" 
                fontSize={11} 
                interval={0} 
                angle={-45} 
                textAnchor="end" 
              />
              <YAxis stroke="#64748b" fontSize={11} unit=" ms" />
              <Tooltip 
                contentStyle={{ backgroundColor: '#090d16', borderColor: '#334155', borderRadius: '0.75rem', fontSize: '12px' }}
                formatter={(val: any, name: any) => [`${val} ms`, name === 'Go' ? 'Go Puro (mediana)' : 'Rust Puro (mediana)']}
                labelFormatter={(label, payload) => payload?.[0]?.payload?.fullName || label}
              />
              <Legend verticalAlign="top" height={36} />
              <Bar dataKey="Go" fill="#06b6d4" radius={[4, 4, 0, 0]} name="Go Puro (ms)" />
              <Bar dataKey="Rust" fill="#f97316" radius={[4, 4, 0, 0]} name="Rust Puro (ms)" />
            </BarChart>
          </ResponsiveContainer>
        )}

        {activeTab === 'operations' && (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={opData} margin={{ top: 10, right: 10, left: -20, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="op" stroke="#64748b" fontSize={12} />
              <YAxis stroke="#64748b" fontSize={12} unit=" tarefas" />
              <Tooltip 
                contentStyle={{ backgroundColor: '#090d16', borderColor: '#334155', borderRadius: '0.75rem', fontSize: '12px' }}
                formatter={(val: any, name: any) => [`${val} vitórias`, name]}
              />
              <Legend verticalAlign="top" height={36} />
              <Bar dataKey="Rust" fill="#f97316" stackId="a" radius={[0, 0, 0, 0]} name="Rust Puro" />
              <Bar dataKey="Go" fill="#06b6d4" stackId="a" radius={[0, 0, 0, 0]} name="Go Puro" />
              <Bar dataKey="Empates" fill="#a855f7" stackId="a" radius={[4, 4, 0, 0]} name="Empate Estatístico" />
            </BarChart>
          </ResponsiveContainer>
        )}

        {activeTab === 'bytes' && (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={bytesData} margin={{ top: 10, right: 10, left: -20, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis 
                dataKey="name" 
                stroke="#64748b" 
                fontSize={11} 
                interval={0} 
                angle={-45} 
                textAnchor="end" 
              />
              <YAxis stroke="#64748b" fontSize={11} unit=" KB" />
              <Tooltip 
                contentStyle={{ backgroundColor: '#090d16', borderColor: '#334155', borderRadius: '0.75rem', fontSize: '12px' }}
                formatter={(val: any, name: any) => [`${val} KB`, name === 'GoKB' ? 'Tamanho Go' : 'Tamanho Rust']}
                labelFormatter={(label, payload) => payload?.[0]?.payload?.fullName || label}
              />
              <Legend verticalAlign="top" height={36} />
              <Bar dataKey="GoKB" fill="#06b6d4" radius={[4, 4, 0, 0]} name="Go (KB)" />
              <Bar dataKey="RustKB" fill="#f97316" radius={[4, 4, 0, 0]} name="Rust (KB)" />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

    </div>
  );
}
