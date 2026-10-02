# Decisão 0001: custo de `init()` do `gen2brain/jxl` no engine Go

Status: aceita (issue #17). Data: 2026-10-02.

## Contexto

Todo processo do engine Go paga o `init()` de `github.com/gen2brain/jxl` v0.2.0 no import, antes de
`main`. Medido com `GODEBUG=inittrace=1 go/bin/arena-batch --op analyze --input /dev/null`:

| Pacote | Tempo de init | Alocação |
|---|---|---|
| `github.com/gen2brain/jxl` | 38 ms | 2,1 MB |
| `github.com/gen2brain/gav1d/av1` | 1,0 ms | 0,25 MB |
| todos os demais somados | ~1,5 ms | < 0,1 MB |

O `quantweights.go` do pacote chama `computeQuantTable` para todas as tabelas no import, e `dct.go` e
`transform.go` também montam tabelas. O startup medido do `arena-batch` é 45 ms no Go e 1,6 ms no Rust.
Como o init roda no import de um pacote de terceiros, o nosso código não consegue torná-lo preguiçoso.

## Opções

1. **Contribuir upstream** com `sync.Once` nas tabelas do `jxl`. Remove o custo para todos os usuários da
   biblioteca, mas depende de aceitação e de release.
2. **Separar o `arena-batch` por formato**, para que PNG, JPEG e WebP não paguem o init do JXL.
3. **Manter o custo e reportá-lo à parte.** O harness já faz isso: o modo `batch` mede o startup de cada
   binário separadamente e mostra a coluna "líquido de startup"; o modo `http` mede o tempo de codec que o
   servidor reporta, e o servidor paga o init uma vez, na partida, fora de qualquer requisição medida.

## Decisão

**Opção 3, com a opção 1 como acompanhamento não bloqueante.**

- A opção 2 foi **recusada**. Ela mudaria o produto medido: o benchmark compara os binários que um usuário
  de verdade executaria, e quem usa o `arena-batch` com JXL paga esses 38 ms. Separar por formato esconderia
  um custo real do Go atrás de uma escolha de empacotamento, multiplicaria os binários (um por formato, mais
  os Dockerfiles e o CI) e não alteraria o servidor, onde o init já acontece uma única vez.
- O custo continua visível: o pódio em modo `batch` é, por construção, "processo completo" e diz isso; a
  velocidade de codec vem do modo `http`.
- Para o custo fixo pesar menos na leitura do throughput, o corpus ganhou uma versão de 4,19 MP
  (`python3 harness/generators/make_corpus.py --large`, ver README). Em 0,26 MP, 45 ms de startup
  equivalem a mais que o tempo de codec de uma imagem; em 4 MP isso deixa de acontecer.
- Seguimento recomendado, fora do escopo desta mudança por ser uma contribuição a um repositório de
  terceiros: abrir issue ou PR em `gen2brain/jxl` com `sync.Once` em `computeQuantTable` e nas tabelas de
  `dct.go` e `transform.go`. Se for aceito e liberado, basta atualizar o `go.mod`; nenhuma mudança no
  harness é necessária, porque o startup é medido, não assumido.

## Consequências

- Resultados do modo `batch` não devem ser lidos como velocidade de codec (as notas dos relatórios dizem isso).
- O startup do Go deve cair sozinho quando a dependência corrigir o init; o relatório mostra a diferença.
