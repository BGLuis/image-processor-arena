'use client';

import React from 'react';
import dynamic from 'next/dynamic';
import { DataProvider } from '../context/DataContext';
import TopBar from '../components/TopBar';
import Footer from '../components/Footer';

// Componentes com estado do navegador e DuckDB-Wasm
const FilterToolbar = dynamic(() => import('../components/FilterToolbar'), { ssr: false });
const PodiumSection = dynamic(() => import('../components/PodiumSection'), { ssr: false });
const BestPerLanguage = dynamic(() => import('../components/BestPerLanguage'), { ssr: false });
const LeaderboardTable = dynamic(() => import('../components/LeaderboardTable'), { ssr: false });
const HeatmapSection = dynamic(() => import('../components/HeatmapSection'), { ssr: false });
const DuelSection = dynamic(() => import('../components/DuelSection'), { ssr: false });
const SqlConsoleSection = dynamic(() => import('../components/SqlConsoleSection'), { ssr: false });

export default function Home() {
  return (
    <DataProvider>
      <div className="min-h-screen bg-[#0a0c0f] text-[#eceff3] flex flex-col selection:bg-[#2ec4e6]/30 selection:text-[#eceff3]">
        
        {/* Barra Superior */}
        <TopBar />

        {/* Conteúdo Principal */}
        <main className="flex-1 max-w-[1400px] w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
          
          {/* Barra de Filtros Sticky */}
          <FilterToolbar />

          {/* Seção 1: Pódio */}
          <PodiumSection />

          {/* Seção 2: Melhor por Linguagem */}
          <BestPerLanguage />

          {/* Seção 3: Leaderboard / Ranking Interativo */}
          <LeaderboardTable />

          {/* Seção 4: Heatmap Tarefa × Implementação */}
          <HeatmapSection />

          {/* Seção 5: Duelo Par-a-Par com PSNR Equivalente */}
          <DuelSection />

          {/* Seção 6: Console SQL Interativo */}
          <SqlConsoleSection />

        </main>

        {/* Rodapé */}
        <Footer />

      </div>
    </DataProvider>
  );
}
