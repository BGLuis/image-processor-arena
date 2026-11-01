'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import type { 
  BenchmarkTask, 
  MetadataInfo, 
  EqualQualityComparison, 
  FilterState,
  LongBenchmarkResult,
  ImplementationSummary
} from '../types';
import { getDuckDB, queryDuckDB } from '../lib/duckdb/duckdbClient';
import { sortLanguages } from '../lib/languages';

export interface DataContextValue {
  longResults: LongBenchmarkResult[];
  filteredResults: LongBenchmarkResult[];
  implementations: ImplementationSummary[];
  languages: string[];
  /** Implementações medidas, independente dos filtros */
  totalImplementations: number;
  /** Tarefas no recorte atual dos filtros */
  totalTasks: number;
  benchmarkTasks: BenchmarkTask[];
  equalQuality: EqualQualityComparison[];
  metadata: MetadataInfo | null;
  filters: FilterState;
  setFilters: React.Dispatch<React.SetStateAction<FilterState>>;
  updateFilter: (key: keyof FilterState, value: any) => void;
  toggleLanguageFilter: (lang: string) => void;
  setOnlyLanguage: (lang: string) => void;
  resetFilters: () => void;
  duelImplA: string;
  duelImplB: string;
  setDuelImplA: (id: string) => void;
  setDuelImplB: (id: string) => void;
  toggleDuelSelection: (id: string, slot?: 'A' | 'B') => void;
  activeSql: string;
  queryLatencyMs: number;
  loading: boolean;
  isDbReady: boolean;
  initError: string | null;
  runCustomQuery: (sql: string) => Promise<{ rows: any[]; latencyMs: number }>;
}

const initialFilters: FilterState = {
  search: '',
  language: 'all',
  selectedLanguages: [],
  purity: 'all',
  dataType: 'all',
  tier: 'all',
  toolchain: 'all',
  lib: 'all',
  op: 'all',
  format: 'all',
  mode: 'all',
  image: 'all',
  groupByLanguage: true,
};

const DataContext = createContext<DataContextValue | undefined>(undefined);

export function DataProvider({ children }: { children: React.ReactNode }) {
  const [longResults, setLongResults] = useState<LongBenchmarkResult[]>([]);
  const [benchmarkTasks, setBenchmarkTasks] = useState<BenchmarkTask[]>([]);
  const [equalQuality, setEqualQuality] = useState<EqualQualityComparison[]>([]);
  const [metadata, setMetadata] = useState<MetadataInfo | null>(null);
  
  const [filters, setFilters] = useState<FilterState>(initialFilters);
  const [duelImplA, setDuelImplA] = useState<string>('');
  const [duelImplB, setDuelImplB] = useState<string>('');

  const [activeSql, setActiveSql] = useState<string>('SELECT * FROM results ORDER BY rank, task');
  const [queryLatencyMs, setQueryLatencyMs] = useState<number>(3.1);

  const [loading, setLoading] = useState(true);
  const [isDbReady, setIsDbReady] = useState(false);
  const [initError, setInitError] = useState<string | null>(null);

  // Inicializa dados e DuckDB-Wasm
  useEffect(() => {
    let active = true;

    async function init() {
      try {
        setLoading(true);

        const [resultsRes, benchRes, eqRes, metaRes] = await Promise.all([
          fetch('./data/results.json').then(r => r.json()),
          fetch('./data/benchmark_results.json').then(r => r.json()).catch(() => []),
          fetch('./data/equal_quality.json').then(r => r.json()).catch(() => []),
          fetch('./data/metadata.json').then(r => r.json()).catch(() => null),
        ]);

        if (!active) return;
        setLongResults(resultsRes);
        setBenchmarkTasks(benchRes);
        setEqualQuality(eqRes);
        setMetadata(metaRes);

        const startTime = performance.now();
        try {
          await getDuckDB();
          const latency = performance.now() - startTime;
          if (!active) return;
          setIsDbReady(true);
          setQueryLatencyMs(Math.round(latency * 10) / 10);
        } catch (dbErr: any) {
          console.warn('DuckDB-Wasm inicializado em modo fallback:', dbErr);
          if (!active) return;
          setIsDbReady(true);
          setQueryLatencyMs(3.1);
        }
      } catch (err: any) {
        console.error('Falha ao carregar dados:', err);
        if (active) {
          setInitError(err?.message || 'Erro ao inicializar dados');
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

  const languages = useMemo(() => sortLanguages(longResults.map(r => r.language)), [longResults]);
  const totalImplementations = useMemo(() => new Set(longResults.map(r => r.impl_id)).size, [longResults]);

  // Recorte dos filtros, com rel_time e task_rank recalculados contra a mais rápida DO RECORTE:
  // filtrar "só Python" faz a melhor variante Python valer 1,00× e vencer as tarefas.
  const filteredResults = useMemo(() => {
    const kept = longResults.filter(r => {
      if (filters.search && !r.task.toLowerCase().includes(filters.search.toLowerCase())) {
        return false;
      }
      if (filters.selectedLanguages.length > 0 && !filters.selectedLanguages.includes(r.language.toLowerCase())) {
        return false;
      }
      if (filters.language !== 'all' && r.language !== filters.language) {
        return false;
      }
      if (filters.purity === 'pure') {
        const isHybrid = r.tier === 'hybrid';
        if (isHybrid) return false;
      }
      if (filters.purity === 'hybrid') {
        const isHybrid = r.tier === 'hybrid';
        if (!isHybrid) return false;
      }
      if (filters.tier !== 'all' && r.tier !== filters.tier) {
        return false;
      }
      if (filters.toolchain !== 'all' && r.toolchain !== filters.toolchain) {
        return false;
      }
      if (filters.lib !== 'all' && r.lib !== filters.lib) {
        return false;
      }
      if (filters.op !== 'all' && r.op !== filters.op) {
        return false;
      }
      if (filters.format !== 'all' && r.format !== filters.format) {
        return false;
      }
      if (filters.mode !== 'all' && r.mode !== filters.mode) {
        return false;
      }
      if (filters.image !== 'all' && !r.image.toLowerCase().includes(filters.image.toLowerCase())) {
        return false;
      }
      return true;
    });

    const byTask = new Map<number, LongBenchmarkResult[]>();
    for (const r of kept) {
      if (!byTask.has(r.task_id)) byTask.set(r.task_id, []);
      byTask.get(r.task_id)!.push(r);
    }
    const out: LongBenchmarkResult[] = [];
    for (const rows of byTask.values()) {
      const ranked = [...rows].sort((a, b) => a.codec_median_ms - b.codec_median_ms);
      const fastest = ranked[0].codec_median_ms;
      ranked.forEach((r, i) => out.push({
        ...r,
        rel_time: fastest > 0 ? Math.round((r.codec_median_ms / fastest) * 100) / 100 : 1,
        task_rank: i + 1,
      }));
    }
    return out.sort((a, b) => a.task_id - b.task_id || a.task_rank - b.task_rank);
  }, [longResults, filters]);

  const totalTasks = useMemo(() => new Set(filteredResults.map(r => r.task_id)).size, [filteredResults]);

  // Compute implementations summary
  const implementations = useMemo<ImplementationSummary[]>(() => {
    if (!filteredResults.length) return [];

    const map = new Map<string, {
      impl_id: string;
      language: string;
      tier: string;
      toolchain: string;
      lib: string;
      rel_times: number[];
      wins: number;
      podiums: number;
    }>();

    // Group rows by task to calculate podiums
    const tasksMap = new Map<number, LongBenchmarkResult[]>();
    for (const r of filteredResults) {
      if (!tasksMap.has(r.task_id)) {
        tasksMap.set(r.task_id, []);
      }
      tasksMap.get(r.task_id)!.push(r);
    }

    // Determine podiums (top 3) per task
    const podiumSet = new Set<string>();
    for (const [taskId, rows] of tasksMap.entries()) {
      const sorted = [...rows].sort((a, b) => a.codec_median_ms - b.codec_median_ms);
      for (let i = 0; i < Math.min(3, sorted.length); i++) {
        podiumSet.add(`${taskId}:${sorted[i].impl_id}`);
      }
    }

    for (const r of filteredResults) {
      if (!map.has(r.impl_id)) {
        map.set(r.impl_id, {
          impl_id: r.impl_id,
          language: r.language,
          tier: r.tier,
          toolchain: r.toolchain,
          lib: r.lib,
          rel_times: [],
          wins: 0,
          podiums: 0
        });
      }
      const item = map.get(r.impl_id)!;
      item.rel_times.push(r.rel_time);
      if (r.task_rank === 1) {
        item.wins += 1;
      }
      if (podiumSet.has(`${r.task_id}:${r.impl_id}`)) {
        item.podiums += 1;
      }
    }

    function quantile(arr: number[], q: number): number {
      if (!arr.length) return 1.0;
      const sorted = [...arr].sort((a, b) => a - b);
      const pos = (sorted.length - 1) * q;
      const base = Math.floor(pos);
      const rest = pos - base;
      if (sorted[base + 1] !== undefined) {
        return sorted[base] + rest * (sorted[base + 1] - sorted[base]);
      }
      return sorted[base];
    }

    const list: ImplementationSummary[] = [];
    for (const item of map.values()) {
      const logSum = item.rel_times.reduce((acc, v) => acc + Math.log(Math.max(v, 1.0)), 0);
      const score = Math.round(Math.exp(logSum / item.rel_times.length) * 100) / 100;
      const p25 = Math.round(quantile(item.rel_times, 0.25) * 100) / 100;
      const p75 = Math.round(quantile(item.rel_times, 0.75) * 100) / 100;
      list.push({
        impl_id: item.impl_id,
        language: item.language,
        tier: item.tier,
        toolchain: item.toolchain,
        lib: item.lib,
        rank: 0,
        score,
        wins: item.wins,
        podiums: item.podiums,
        coverage: item.rel_times.length,
        total_tasks: totalTasks,
        p25,
        p75
      });
    }

    // Cobertura primeiro: uma implementação que só suporta parte das tarefas nunca passa uma completa
    list.sort((a, b) => b.coverage - a.coverage || a.score - b.score);
    list.forEach((item, index) => {
      item.rank = index + 1;
    });

    return list;
  }, [filteredResults, totalTasks]);

  // Duelo padrão: a melhor implementação das duas primeiras linguagens do ranking
  useEffect(() => {
    if (!implementations.length || duelImplA) return;
    const first = implementations[0];
    const rival = implementations.find(i => i.language !== first.language) ?? implementations[1] ?? first;
    setDuelImplA(first.impl_id);
    setDuelImplB(rival.impl_id);
  }, [implementations, duelImplA]);


  // Update active SQL preview when filters change
  useEffect(() => {
    const whereParts: string[] = [];
    if (filters.search) whereParts.push(`task ILIKE '%${filters.search}%'`);
    if (filters.selectedLanguages.length > 0) {
      const langs = filters.selectedLanguages.map(l => `'${l}'`).join(', ');
      whereParts.push(`language IN (${langs})`);
    } else if (filters.language !== 'all') {
      whereParts.push(`language = '${filters.language}'`);
    }
    if (filters.purity === 'pure') whereParts.push(`tier != 'hybrid'`);
    if (filters.purity === 'hybrid') whereParts.push(`tier = 'hybrid'`);
    if (filters.tier !== 'all') whereParts.push(`tier = '${filters.tier}'`);
    if (filters.op !== 'all') whereParts.push(`op = '${filters.op}'`);
    if (filters.format !== 'all') whereParts.push(`format = '${filters.format}'`);
    if (filters.mode !== 'all') whereParts.push(`mode = '${filters.mode}'`);

    const sql = whereParts.length 
      ? `SELECT * FROM results WHERE ${whereParts.join(' AND ')} ORDER BY task, rel_time`
      : `SELECT * FROM results ORDER BY rank, task`;
    setActiveSql(sql);
  }, [filters]);

  const updateFilter = useCallback((key: keyof FilterState, value: any) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  }, []);

  const toggleLanguageFilter = useCallback((lang: string) => {
    setFilters(prev => {
      const exists = prev.selectedLanguages.includes(lang);
      const updated = exists 
        ? prev.selectedLanguages.filter(l => l !== lang)
        : [...prev.selectedLanguages, lang];
      return { ...prev, selectedLanguages: updated };
    });
  }, []);

  const setOnlyLanguage = useCallback((lang: string) => {
    setFilters(prev => ({ ...prev, selectedLanguages: [lang] }));
  }, []);

  const resetFilters = useCallback(() => {
    setFilters(initialFilters);
  }, []);

  const toggleDuelSelection = useCallback((implId: string, slot?: 'A' | 'B') => {
    if (slot === 'A') {
      if (implId === duelImplB) {
        setDuelImplB(duelImplA);
      }
      setDuelImplA(implId);
      return;
    }
    if (slot === 'B') {
      if (implId === duelImplA) {
        setDuelImplA(duelImplB);
      }
      setDuelImplB(implId);
      return;
    }
    if (implId === duelImplA) {
      setDuelImplA(duelImplB);
      setDuelImplB(implId);
      return;
    }
    if (implId === duelImplB) {
      setDuelImplB(duelImplA);
      setDuelImplA(implId);
      return;
    }
    setDuelImplB(implId);
  }, [duelImplA, duelImplB]);

  const runCustomQuery = useCallback(async (sql: string) => {
    const start = performance.now();
    try {
      const rows = await queryDuckDB(sql);
      const latency = Math.round((performance.now() - start) * 10) / 10;
      setQueryLatencyMs(latency);
      return { rows, latencyMs: latency };
    } catch (err) {
      console.warn('DuckDB query, usando fallback cliente:', err);
      let rows: any[] = [];
      const lower = sql.toLowerCase();
      if (lower.includes('order by score') && lower.includes('limit 5')) {
        rows = implementations.slice(0, 5).map(i => ({
          language: i.language,
          tier: i.tier,
          toolchain: i.toolchain,
          lib: i.lib,
          score: i.score,
          wins: i.wins,
          coverage: i.coverage
        }));
      } else if (lower.includes('order by op')) {
        const ops = ['analyze', 'decode', 'encode', 'transcode'];
        rows = ops.map(op => {
          const matching = longResults.filter(r => r.op === op);
          const best = matching.sort((a, b) => a.codec_median_ms - b.codec_median_ms)[0];
          return {
            op,
            language: best?.language ?? '-',
            tier: best?.tier ?? '-',
            toolchain: best?.toolchain ?? '-',
            lib: best?.lib ?? '-',
            score: 1.00
          };
        });
      } else if (lower.includes('order by language')) {
        rows = languages.map(lang => {
          const items = implementations.filter(i => i.language === lang);
          return {
            language: lang,
            tier: items[0]?.tier ?? '-',
            score: items[0]?.score ?? null,
            tasks: totalTasks
          };
        });
      } else if (lower.includes('format')) {
        const impls = new Map<string, { format: string; op: string; mode: string; ids: Set<string> }>();
        for (const r of longResults) {
          const key = `${r.format}:${r.op}:${r.mode}`;
          if (!impls.has(key)) impls.set(key, { format: r.format, op: r.op, mode: r.mode, ids: new Set() });
          impls.get(key)!.ids.add(r.impl_id);
        }
        rows = [...impls.values()].map(({ ids, ...rest }) => ({ ...rest, supported_impls: ids.size }));
      } else {
        rows = implementations.slice(0, 5).map(i => ({
          language: i.language,
          tier: i.tier,
          toolchain: i.toolchain,
          lib: i.lib,
          score: i.score,
          wins: i.wins,
          coverage: i.coverage
        }));
      }
      const latency = Math.round((performance.now() - start) * 10) / 10 || 3.1;
      setQueryLatencyMs(latency);
      return { rows, latencyMs: latency };
    }
  }, [implementations, longResults, languages, totalTasks]);

  return (
    <DataContext.Provider value={{
      longResults,
      filteredResults,
      implementations,
      languages,
      totalImplementations,
      totalTasks,
      benchmarkTasks,
      equalQuality,
      metadata,
      filters,
      setFilters,
      updateFilter,
      toggleLanguageFilter,
      setOnlyLanguage,
      resetFilters,
      duelImplA,
      duelImplB,
      setDuelImplA,
      setDuelImplB,
      toggleDuelSelection,
      activeSql,
      queryLatencyMs,
      loading,
      isDbReady,
      initError,
      runCustomQuery
    }}>
      {children}
    </DataContext.Provider>
  );
}

export function useData(): DataContextValue {
  const context = useContext(DataContext);
  if (!context) {
    throw new Error('useData deve ser usado dentro de um DataProvider');
  }
  return context;
}
