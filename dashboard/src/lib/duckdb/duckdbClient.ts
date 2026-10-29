import type { AsyncDuckDB, AsyncDuckDBConnection } from '@duckdb/duckdb-wasm';

let dbInstance: AsyncDuckDB | null = null;
let connInstance: AsyncDuckDBConnection | null = null;
let isInitializing = false;
let initPromise: Promise<AsyncDuckDBConnection> | null = null;

export async function getDuckDB(): Promise<{ db: AsyncDuckDB; conn: AsyncDuckDBConnection }> {
  if (connInstance && dbInstance) {
    return { db: dbInstance, conn: connInstance };
  }

  if (isInitializing && initPromise) {
    await initPromise;
    if (connInstance && dbInstance) {
      return { db: dbInstance, conn: connInstance };
    }
  }

  isInitializing = true;
  initPromise = (async () => {
    try {
      const duckdb = await import('@duckdb/duckdb-wasm');
      
      // Carrega os bundles oficiais via JSDelivr CDN
      const JSDELIVR_BUNDLES = duckdb.getJsDelivrBundles();
      const bundle = await duckdb.selectBundle(JSDELIVR_BUNDLES);
      
      const worker = new Worker(bundle.mainWorker!);
      const logger = new duckdb.ConsoleLogger();
      const db = new duckdb.AsyncDuckDB(logger, worker);
      
      await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
      const conn = await db.connect();

      // Carregar os dados de benchmark_results.json
      const response = await fetch('./data/benchmark_results.json');
      if (!response.ok) {
        throw new Error(`Falha ao buscar dados: ${response.status} ${response.statusText}`);
      }
      const jsonData = await response.text();
      
      await db.registerFileText('benchmark_results.json', jsonData);
      
      // Criar a tabela no DuckDB
      await conn.query(`
        CREATE OR REPLACE TABLE benchmark_results AS 
        SELECT * FROM read_json_auto('benchmark_results.json');
      `);

      dbInstance = db;
      connInstance = conn;
      return conn;
    } finally {
      isInitializing = false;
    }
  })();

  await initPromise;
  if (!dbInstance || !connInstance) {
    throw new Error('Falha na inicialização do DuckDB-Wasm');
  }

  return { db: dbInstance, conn: connInstance };
}

export async function queryDuckDB<T = any>(sql: string): Promise<T[]> {
  const { conn } = await getDuckDB();
  const arrowResult = await conn.query(sql);
  
  const rows: T[] = arrowResult.toArray().map((row: any) => {
    const json = row.toJSON();
    for (const key in json) {
      if (typeof json[key] === 'bigint') {
        json[key] = Number(json[key]);
      }
    }
    return json as T;
  });

  return rows;
}
