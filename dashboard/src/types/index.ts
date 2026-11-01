export interface LongBenchmarkResult {
  task_id: number;
  task: string;
  op: 'analyze' | 'encode' | 'decode' | 'transcode' | string;
  format: string;
  mode: 'lossy' | 'lossless' | string;
  image: string;
  mp: number;
  language: 'rust' | 'go' | 'cpp' | 'python' | string;
  tier: 'portable' | 'accelerated' | 'hybrid' | string;
  toolchain: string;
  lib: string;
  impl_id: string;
  codec_median_ms: number;
  p25: number;
  p75: number;
  bytes: number;
  psnr_db: number | null;
  rel_time: number;
  /** 1 = mais rápida da tarefa entre as implementações que a suportam */
  task_rank: number;
}

export interface ImplementationSummary {
  impl_id: string;
  language: string;
  tier: string;
  toolchain: string;
  lib: string;
  rank: number;
  score: number;
  wins: number;
  podiums: number;
  coverage: number;
  total_tasks: number;
  p25: number;
  p75: number;
}

export interface FilterState {
  search: string;
  language: string;
  selectedLanguages: string[];
  purity: 'all' | 'pure' | 'hybrid';
  dataType: 'all' | 'real';
  tier: string;
  toolchain: string;
  lib: string;
  op: string;
  format: string;
  mode: string;
  image: string;
  groupByLanguage: boolean;
}

export interface BenchmarkTask {
  id: number;
  task: string;
  op: 'analyze' | 'encode' | 'decode' | 'transcode' | string;
  format: string;
  mode: 'lossy' | 'lossless' | string;
  image: string;
  mp: number;
  metric: string;
  q_go: number | null;
  q_rust: number | null;
  winner: 'Rust' | 'Go' | 'Empate' | string;
  speedup: number;
  speedup_factor: number | null;
  bytes_ratio: number | null;
  
  // Go
  go_codec_median_ms: number | null;
  go_codec_p25_ms: number | null;
  go_codec_p75_ms: number | null;
  go_codec_min_ms: number | null;
  go_codec_max_ms: number | null;
  go_wall_median_ms: number | null;
  go_throughput_mp_s: number | null;
  go_bytes: number;
  go_psnr_db: number | null;
  go_exact: boolean;

  // Rust
  rust_codec_median_ms: number | null;
  rust_codec_p25_ms: number | null;
  rust_codec_p75_ms: number | null;
  rust_codec_min_ms: number | null;
  rust_codec_max_ms: number | null;
  rust_wall_median_ms: number | null;
  rust_throughput_mp_s: number | null;
  rust_bytes: number;
  rust_psnr_db: number | null;
  rust_exact: boolean;
}

export interface PerOperationSummary {
  op: string;
  tasks: number;
  go_wins: number;
  rust_wins: number;
  ties: number;
  geomean_go_over_rust: number;
}

export interface EqualQualityComparison {
  task: string;
  format: string;
  image: string;
  target_psnr_db: number;
  go_q: number;
  rust_q: number;
  go_psnr_db?: number;
  rust_psnr_db?: number;
  psnr_go?: number;
  psnr_rust?: number;
  go_bytes: number;
  rust_bytes: number;
  bytes_ratio: number;
  metric?: string;
  go_time_ms: {
    median: number;
    p25: number;
    p75: number;
    min?: number;
    max?: number;
    n?: number;
  };
  rust_time_ms: {
    median: number;
    p25: number;
    p75: number;
    min?: number;
    max?: number;
    n?: number;
  };
  winner: string;
  speedup: number;
}

export interface MetadataInfo {
  summary: {
    total_tasks: number;
    rust_wins: number;
    go_wins: number;
    ties: number;
    rust_win_percentage: number;
    go_win_percentage: number;
    ties_percentage: number;
    global_geomean: number;
  };
  filters_options: {
    formats: string[];
    ops: string[];
    modes: string[];
    images: string[];
  };
  environment: {
    platform?: string;
    cpu?: string;
    cpu_count?: number;
    python?: string;
    reference_decoder?: string;
  };
  collected_at: string;
  iterations?: number;
  warmup?: number;
  mode: string;
}
