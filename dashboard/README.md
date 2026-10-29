# 🏆 Image Processor Arena — Dashboard Interativo

Dashboard analítico moderno desenvolvido com **Next.js**, **TypeScript**, **Tailwind CSS** e motor de banco de dados analítico in-browser **DuckDB-Wasm** (OLAP via WebAssembly).

---

## 🚀 Como Iniciar

### Pré-requisitos
- **Node.js**: v18+ (recomendado v20+)
- **npm** ou **pnpm** / **yarn**

### Instalação e Execução

```bash
# 1. Entre no diretório do dashboard
cd dashboard

# 2. Instale as dependências (se ainda não o fez)
npm install

# 3. Inicie o servidor de desenvolvimento
npm run dev
```

Abra [http://localhost:3000](http://localhost:3000) no seu navegador para explorar o dashboard.

---

## 🛠️ Arquitetura

- **Framework Web**: [Next.js](https://nextjs.org/) (App Router) + React 19 + TypeScript.
- **Banco de Dados Analítico**: [DuckDB-Wasm](https://github.com/duckdb/duckdb-wasm) rodando 100% no cliente em WebAssembly, permitindo consultas analíticas em SQL ultrarrápidas sem necessidade de servidor de banco de dados externo.
- **Gráficos**: [Recharts](https://recharts.org/) integrados com dados reativos do DuckDB.
- **Estilização**: [Tailwind CSS v4](https://tailwindcss.com/) com design system dark-tech / arena visual.
- **Pipeline de Dados**: `scripts/prepare_dashboard_data.py` converte os resultados da Arena (`results/benchmark_results.json`) em tabelas analíticas para o DuckDB em `dashboard/public/data/`.

---

## 📊 Recursos do Dashboard

1. **Pódio Geral & KPIs**:
   - Razão geométrica global (Rust 2.67x mais rápido).
   - Placar de vitórias e empates estatísticos com intervalos p25-p75.
   - Throughput médio por motor em Megapixels por segundo (MP/s).
2. **Filtros Dinâmicos Reativos**:
   - Por Operação (`analyze`, `encode`, `decode`, `transcode`).
   - Por Formato (`png`, `jpeg`, `webp`, `avif`, `jxl`, `pam`).
   - Por Modo (`lossy`, `lossless`).
   - Por Imagem de Teste (`photo.pam`, `screenshot.pam`, etc.).
   - Busca textual em tempo real.
3. **Visualizações Gráficas**:
   - Comparativo de Throughput (MP/s).
   - Latência de Codec (ms) de servidores.
   - Distribuição de Vitórias por Operação.
   - Razão de Tamanho da Saída (KB).
4. **Comparação a Qualidade Equivalente (Equal PSNR)**:
   - Seção dedicada para AVIF e JXL lossy comparados no mesmo nível de decibéis (PSNR).
5. **Tabela Analítica Completa**:
   - Ordenação dinâmica por qualquer coluna ao clicar no cabeçalho.
6. **Console SQL Interativo (DuckDB-Wasm)**:
   - Permite executar consultas SQL arbitrárias sobre a tabela `benchmark_results` em tempo real.

---

## 🔄 Atualizando os Dados do Benchmark

Sempre que rodar uma nova bateria de testes no harness da Arena:

```bash
# Na raiz do repositório
python3 scripts/prepare_dashboard_data.py
```

Os novos dados serão imediatamente integrados ao `dashboard/public/data/`.

---

## 📦 Build para Produção

```bash
cd dashboard
npm run build
npm run start
```
