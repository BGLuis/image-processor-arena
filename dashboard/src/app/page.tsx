'use client';

import React from 'react';
import dynamic from 'next/dynamic';
import Header from '../components/Header';
import { DataProvider } from '../context/DataContext';

// Importação dinâmica para componentes com DuckDB e Recharts
const KpiCards = dynamic(() => import('../components/KpiCards'), { ssr: false });
const FilterBar = dynamic(() => import('../components/FilterBar'), { ssr: false });
const ChartsSection = dynamic(() => import('../components/ChartsSection'), { ssr: false });
const EqualQualitySection = dynamic(() => import('../components/EqualQualitySection'), { ssr: false });
const ResultsTable = dynamic(() => import('../components/ResultsTable'), { ssr: false });
const SqlConsole = dynamic(() => import('../components/SqlConsole'), { ssr: false });

export default function Home() {
  return (
    <DataProvider>
      <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 flex flex-col">
        {/* Header Superior */}
        <Header />

        {/* Conteúdo Principal */}
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {/* Métricas e KPIs do Pódio */}
          <KpiCards />

          {/* Barra de Filtros Reativos e SQL Preview */}
          <FilterBar />

          {/* Gráficos Interativos */}
          <ChartsSection />

          {/* Seção Especial: Equal PSNR */}
          <EqualQualitySection />

          {/* Tabela Analítica Completa com Ordenação */}
          <ResultsTable />

          {/* Console SQL Interativo DuckDB-Wasm */}
          <SqlConsole />
        </main>

        {/* Rodapé */}
        <footer className="border-t border-slate-900 py-6 mt-12 bg-slate-950/60 text-center text-xs text-slate-500">
          <div className="max-w-7xl mx-auto px-4">
            <p>
              Image Processor Arena · Pureza Absoluta (0% CGO / 0% FFI) · Licenciado sob AGPL-3.0-or-later
            </p>
            <p className="mt-1 font-mono text-[11px] text-slate-600">
              Motor analítico in-browser alimentado por DuckDB-Wasm & Next.js
            </p>
          </div>
        </footer>
      </div>
    </DataProvider>
  );
}
