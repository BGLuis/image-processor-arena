'use client';

import React from 'react';
import dynamic from 'next/dynamic';
import { DataProvider } from '../context/DataContext';
import TopBar from '../components/TopBar';
import Footer from '../components/Footer';

// Componentes com carregamento dinâmico
const FilterToolbar = dynamic(() => import('../components/FilterToolbar'), { ssr: false });
const PodiumSection = dynamic(() => import('../components/PodiumSection'), { ssr: false });
const DuelSection = dynamic(() => import('../components/DuelSection'), { ssr: false });
const TradeoffsSection = dynamic(() => import('../components/TradeoffsSection'), { ssr: false });
const LeaderboardTable = dynamic(() => import('../components/LeaderboardTable'), { ssr: false });
const HeatmapSection = dynamic(() => import('../components/HeatmapSection'), { ssr: false });
const SqlConsoleSection = dynamic(() => import('../components/SqlConsoleSection'), { ssr: false });

export default function Home() {
  return (
    <DataProvider>
      <div className="min-h-screen bg-[var(--arena-canvas)] text-[var(--arena-text-primary)] flex flex-col transition-colors selection:bg-[#C9501C]/20 dark:selection:bg-[#E0703A]/20">
        
        {/* Barra Superior & Navegação Âncora */}
        <TopBar />

        {/* Conteúdo Principal */}
        <main className="flex-1 max-w-[1440px] w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
          
          {/* Barra de Filtros Sticky */}
          <FilterToolbar />

          {/* Seção 01: Pódio & Destaques de Execução (com Melhor por Linguagem e Custo da Pureza) */}
          <PodiumSection />

          {/* Seção 02: Duelo Par-a-Par (A × B) */}
          <DuelSection />

          {/* Seção 03: Velocidade Não É Tudo (Trade-offs e Qualidade Equivalente) */}
          <TradeoffsSection />

          {/* Seção 04: Ranking de Implementações */}
          <LeaderboardTable />

          {/* Seção 05: Matriz Tarefa × Implementação */}
          <HeatmapSection />

          {/* Seção 06: Console SQL Interativo */}
          <SqlConsoleSection />

        </main>

        {/* Rodapé Metodológico em 3 Colunas */}
        <Footer />

      </div>
    </DataProvider>
  );
}
