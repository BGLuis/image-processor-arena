'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import type { 
  BenchmarkTask, 
  MetadataInfo, 
  PerOperationSummary, 
  EqualQualityComparison, 
  FilterState 
} from '../types';
import { getDuckDB, queryDuckDB } from '../lib/duckdb/duckdbClient';

export interface DataContextValue {
  tasks: BenchmarkTask[];
  allTasks: BenchmarkTask[];
  metadata: MetadataInfo | null;
  perOperation: PerOperationSummary[];
  equalQuality: EqualQualityComparison[];
  filters: FilterState;
  setFilters: React.Dispatch<React.SetStateAction<FilterState>>;
  updateFilter: (key: keyof FilterState, value: string) => void;
  resetFilters: () => void;
  loading: boolean;
  isDbReady: boolean;
  initError: string | null;
  activeSql: string;
  runCustomQuery: (sql: string) => Promise<any[]>;
}

const initialFilters: FilterState = {
  op: 'all',
  format: 'all',
  mode: 'all',
  image: 'all',
  winner: 'all',
  search: '',
};

const DataContext = createContext<DataContextValue | undefined>(undefined);

export function DataProvider({ children }: { children: React.ReactNode }) {
  const [tasks, setTasks] = useState<BenchmarkTask[]>([]);
  const [allTasks, setAllTasks] = useState<BenchmarkTask[]>([]);
  const [metadata, setMetadata] = useState<MetadataInfo | null>(null);
  const [perOperation, setPerOperation] = useState<PerOperationSummary[]>([]);
  const [equalQuality, setEqualQuality] = useState<EqualQualityComparison[]>([]);
  
  const [filters, setFilters] = useState<FilterState>(initialFilters);
  const [loading, setLoading] = useState(true);
  const [isDbReady, setIsDbReady] = useState(false);
  const [initError, setInitError] = useState<string | null>(null);
  const [activeSql, setActiveSql] = useState<string>('SELECT * FROM benchmark_results');

  // Inicializa dados e DuckDB
  useEffect(() => {
    let active = true;

    async function init() {
      try {
        setLoading(true);

        // 1. Carrega dados estáticos auxiliares
        const [metaRes, perOpRes, eqRes, benchRes] = await Promise.all([
          fetch('./data/metadata.json').then(r => r.json()),
          fetch('./data/per_operation.json').then(r => r.json()),
          fetch('./data/equal_quality.json').then(r => r.json()),
          fetch('./data/benchmark_results.json').then(r => r.json()),
        ]);

        if (!active) return;
        setMetadata(metaRes);
        setPerOperation(perOpRes);
        setEqualQuality(eqRes);
        setAllTasks(benchRes);
        setTasks(benchRes);

        // 2. Inicializa o motor DuckDB-Wasm
        await getDuckDB();
        if (!active) return;
        setIsDbReady(true);
      } catch (err: any) {
        console.error('Falha ao inicializar DuckDB-Wasm:', err);
        if (active) {
          setInitError(err?.message || 'Erro ao inicializar DuckDB-Wasm');
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    init();
    return () => {
      active = false;
    };
  }, []);

  // Constrói cláusula WHERE baseada nos filtros
  const buildWhereClause = useCallback((): string => {
    const conditions: string[] = [];

    if (filters.op && filters.op !== 'all') {
      conditions.push(`op = '${filters.op.replace(/'/g, "''")}'`);
    }
    if (filters.format && filters.format !== 'all') {
      conditions.push(`format = '${filters.format.replace(/'/g, "''")}'`);
    }
    if (filters.mode && filters.mode !== 'all') {
      conditions.push(`mode = '${filters.mode.replace(/'/g, "''")}'`);
    }
    if (filters.image && filters.image !== 'all') {
      conditions.push(`image = '${filters.image.replace(/'/g, "''")}'`);
    }
    if (filters.winner && filters.winner !== 'all') {
      conditions.push(`winner = '${filters.winner.replace(/'/g, "''")}'`);
    }
    if (filters.search && filters.search.trim() !== '') {
      const term = filters.search.trim().toLowerCase().replace(/'/g, "''");
      conditions.push(`(lower(task) LIKE '%${term}%' OR lower(op) LIKE '%${term}%' OR lower(format) LIKE '%${term}%')`);
    }

    return conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
  }, [filters]);

  // Executa query SQL no DuckDB sempre que os filtros mudarem
  useEffect(() => {
    const whereClause = buildWhereClause();
    const sql = `SELECT * FROM benchmark_results ${whereClause} ORDER BY id ASC;`;
    setActiveSql(sql);

    let active = true;

    async function applyFilters() {
      if (isDbReady) {
        try {
          const results = await queryDuckDB<BenchmarkTask>(sql);
          if (active) setTasks(results);
        } catch (err) {
          console.warn('Erro ao executar query no DuckDB, aplicando fallback em memória:', err);
          if (active) fallbackFilter();
        }
      } else {
        fallbackFilter();
      }
    }

    function fallbackFilter() {
      if (!allTasks.length) return;
      const filtered = allTasks.filter(item => {
        if (filters.op !== 'all' && item.op !== filters.op) return false;
        if (filters.format !== 'all' && item.format !== filters.format) return false;
        if (filters.mode !== 'all' && item.mode !== filters.mode) return false;
        if (filters.image !== 'all' && item.image !== filters.image) return false;
        if (filters.winner !== 'all' && item.winner !== filters.winner) return false;
        if (filters.search.trim()) {
          const s = filters.search.toLowerCase();
          return (
            item.task.toLowerCase().includes(s) ||
            item.op.toLowerCase().includes(s) ||
            item.format.toLowerCase().includes(s)
          );
        }
        return true;
      });
      if (active) setTasks(filtered);
    }

    applyFilters();

    return () => {
      active = false;
    };
  }, [filters, isDbReady, allTasks, buildWhereClause]);

  const updateFilter = useCallback((key: keyof FilterState, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  }, []);

  const resetFilters = useCallback(() => {
    setFilters(initialFilters);
  }, []);

  const runCustomQuery = useCallback(async (sql: string) => {
    if (!isDbReady) {
      throw new Error('DuckDB ainda não está pronto.');
    }
    return await queryDuckDB(sql);
  }, [isDbReady]);

  const value = useMemo<DataContextValue>(() => ({
    tasks,
    allTasks,
    metadata,
    perOperation,
    equalQuality,
    filters,
    setFilters,
    updateFilter,
    resetFilters,
    loading,
    isDbReady,
    initError,
    activeSql,
    runCustomQuery,
  }), [
    tasks,
    allTasks,
    metadata,
    perOperation,
    equalQuality,
    filters,
    updateFilter,
    resetFilters,
    loading,
    isDbReady,
    initError,
    activeSql,
    runCustomQuery,
  ]);

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

export function useData(): DataContextValue {
  const context = useContext(DataContext);
  if (!context) {
    throw new Error('useData deve ser usado dentro de um DataProvider');
  }
  return context;
}
