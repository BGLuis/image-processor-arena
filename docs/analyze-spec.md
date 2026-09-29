# Especificação Formal — `op=analyze`

| Campo | Valor |
|---|---|
| **Documento** | Especificação Técnica e Matemática dos Algoritmos de Análise de Imagem |
| **Versão** | 1.0.0 |
| **Status** | Aprovado para Implementação em Go e Rust |
| **Referência** | `docs/reports/ARENA-PROCESSAMENTO-IMAGENS.md` (Seção 2.9) |
| **Objetivo** | Garantir paridade bit-a-bit para métricas inteiras e tolerâncias rigorosas $\epsilon$ para métricas float entre Go e Rust |

---

## 1. Visão Geral e Modelo de Execução

Na arena de processamento de imagens, a operação `analyze` é a única que **não** compara bibliotecas de terceiros: ambas as implementações (em Go puro e Rust puro) são escritas à mão para executar o **mesmo algoritmo sobre as mesmas estruturas de dados**, medindo diretamente a eficiência, latência, alocações de memória e uso de CPU das duas linguagens e seus respectivos runtimes sob carga extrema.

Para que a comparação seja justa e cientificamente válida:
1. **Métricas inteiras e hashes** devem apresentar identidade estrita ($==$) entre Go, Rust e o oráculo matemático em Python.
2. **Métricas de ponto flutuante** devem respeitar limites de tolerância $\epsilon$ pré-definidos decorrentes de arredondamentos de precisão dupla (IEEE 754 float64).
3. Todas as conversões de espaço de cores primárias para Luminância e Crominância ($Y, Cb, Cr$) utilizam **aritmética inteira de ponto fixo** derivada da norma ITU-R BT.601, eliminando divergências de FPU.

---

## 2. Formato de Entrada — PAM P7 Binário

O payload de entrada para `op=analyze` no corpo HTTP e no CLI batch é estritamente o formato binário **Netpbm PAM (Portable Arbitrary Map)** com número mágico `P7`.

### 2.1 Estrutura do Cabeçalho PAM

O cabeçalho é em texto ASCII puro, delimitado por quebras de linha (`\n`), e finalizado pela diretiva `ENDHDR\n`:

```text
P7
WIDTH <largura_em_pixels>
HEIGHT <altura_em_pixels>
DEPTH <3_ou_4>
MAXVAL 255
TUPLTYPE <RGB_ou_RGB_ALPHA>
ENDHDR
```

Regras obrigatórias:
- `WIDTH`: inteiro positivo $W \ge 1$.
- `HEIGHT`: inteiro positivo $H \ge 1$.
- `DEPTH`:
  - `3`: canais $(R, G, B)$, com `TUPLTYPE RGB`.
  - `4`: canais $(R, G, B, A)$, com `TUPLTYPE RGB_ALPHA`.
- `MAXVAL`: fixado obrigatoriamente em `255` (1 byte por amostra). Amostras de 16 bits não são suportadas nesta fase da arena.
- Espaços em branco antes e depois dos valores numéricos devem ser aceitos de acordo com a especificação PAM padrão.
- Comentários iniciados por `#` são permitidos em qualquer ponto do cabeçalho anterior a `ENDHDR`.

### 2.2 Formato da Carga Binária (Raster)

Diretamente após o caractere `\n` da linha `ENDHDR`, seguem os bytes brutos:
- Para `DEPTH 3`: $W \times H \times 3$ bytes no formato entrelaçado $[R_0, G_0, B_0, R_1, G_1, B_1, \dots]$.
- Para `DEPTH 4`: $W \times H \times 4$ bytes no formato entrelaçado $[R_0, G_0, B_0, A_0, R_1, G_1, B_1, A_1, \dots]$.
- Ordem espacial: row-major (varredura da esquerda para a direita, de cima para baixo). O pixel $(0, 0)$ localiza-se no canto superior esquerdo.

---

## 3. Conversão de Cores — BT.601 Inteira

Para eliminar variações de hardware de ponto flutuante, a extração de luminância ($Y$) e crominâncias ($Cb, Cr$) é realizada em aritmética inteira de ponto fixo com 8 bits de precisão fracionária:

$$Y = (77 \cdot R + 150 \cdot G + 29 \cdot B + 128) \gg 8$$

$$Cb = \operatorname{clamp}\left(\left(\left(-43 \cdot R - 85 \cdot G + 128 \cdot B + 128\right) \gg 8\right) + 128, 0, 255\right)$$

$$Cr = \operatorname{clamp}\left(\left(\left(128 \cdot R - 107 \cdot G - 21 \cdot B + 128\right) \gg 8\right) + 128, 0, 255\right)$$

### 3.1 Propriedades da Aritmética Inteira

1. Coeficientes BT.601:
   - $77 + 150 + 29 = 256 = 2^8$.
   - $-43 - 85 + 128 = 0$.
   - $128 - 107 - 21 = 0$.
2. Quando $R = G = B = V$ (cinza neutro):
   - $Y = (256 \cdot V + 128) \gg 8 = V$.
   - $Cb = (128 \gg 8) + 128 = 0 + 128 = 128$.
   - $Cr = (128 \gg 8) + 128 = 0 + 128 = 128$.
3. Deslocamento para a direita com sinal (`>> 8`):
   - Em Go, Rust e Python, o operador `>>` em inteiros com sinal (`int32` ou `i32`) realiza o deslocamento aritmético preservando o sinal: $\lfloor x / 256 \rfloor$.
   - Exemplo: para $R=255, G=0, B=0$, a expressão $-43 \cdot 255 + 128 = -10837$. O deslocamento $-10837 \gg 8 = -43$. Somando 128 obtém-se $85$.
4. Clamping obrigatório:
   - Para $R=255, G=0, B=0$: $128 \cdot 255 + 128 = 32768$. $32768 \gg 8 = 128$. $128 + 128 = 256$. Sem clamping, esse valor causaria overflow em `uint8`. O clamping restringe ao intervalo $[0, 255]$, resultando em $Cr = 255$.
   - Definição: $\operatorname{clamp}(v, 0, 255) = \min(255, \max(0, v))$.

---

## 4. Métricas Inteiras Exatas ($\epsilon = 0$)

Estas métricas devem produzir resultados idênticos em todas as linguagens.

### 4.1 Largura e Altura
- `width`: inteiro $W \in \mathbb{N}^+$.
- `height`: inteiro $H \in \mathbb{N}^+$.

### 4.2 Proporção de Tela (`aspect_ratio`)
- Fração canônica reduzida por MDC (Maior Divisor Comum / GCD):
  $$g = \operatorname{gcd}(W, H)$$
  $$W' = W / g, \quad H' = H / g$$
  - String formatada: `"{W'}:{H'}"` (ex: `"16:9"`, `"4:3"`, `"1:1"`).
- Proporção em ponto flutuante:
  $$\text{float} = \frac{W}{H}$$ (precisão dupla float64).

### 4.3 Alinhamento a Blocos (`block_alignment`)
Avaliado para os 4 tamanhos de bloco canônicos dos codecs de imagem $b \in \{8, 16, 64, 256\}$:
- $b = 8$: bloco DCT básico do JPEG e VarDCT do JPEG XL.
- $b = 16$: macrobloco do VP8 / WebP.
- $b = 64$: superbloco do AV1 / AVIF.
- $b = 256$: grupo modular / VarDCT do JPEG XL.

Para cada $b$:
- `w_mod`: $W \pmod b$.
- `h_mod`: $H \pmod b$.
- `partial_pixels`: Número de pixels da imagem que caem em blocos parciais (blocos que ultrapassam a borda direita ou inferior da imagem).
  $$\text{full\_w} = \lfloor W / b \rfloor \cdot b, \quad \text{full\_h} = \lfloor H / b \rfloor \cdot b$$
  $$\text{partial\_pixels} = (W \cdot H) - (\text{full\_w} \cdot \text{full\_h})$$
- `partial_pct`: Fração de pixels em blocos parciais:
  $$\text{partial\_pct} = \frac{\text{partial\_pixels}}{W \cdot H}$$

### 4.4 Cores Únicas (`unique_colors`)
- Contagem exata do número de tuplas RGBA de 32 bits distintas presentes na imagem.
- Para imagens com `DEPTH 3` (`RGB`), o canal Alpha é implicitamente $255$ (totalmente opaco).
- Codificação de cada pixel como inteiro de 32 bits:
  $$\text{key} = (R \ll 24) \mid (G \ll 16) \mid (B \ll 8) \mid A$$
- Go e Rust devem usar uma tabela hash / conjunto de 32 bits (`hashset` / `map[uint32]struct{}`) para contar a cardinalidade exata.

### 4.5 Cor Dominante e Média (`dominant_color`)
- Quantização de cada canal para 4 bits ($16$ níveis por canal, total $4096$ bins):
  $$R_4 = R \gg 4, \quad G_4 = G \gg 4, \quad B_4 = B \gg 4$$
- Índice no histograma de 4096 posições ($12$ bits):
  $$\text{idx} = (R_4 \ll 8) \mid (G_4 \ll 4) \mid B_4 \in [0, 4095]$$
- Cor dominante (`dominant_bin`): o índice $\text{idx}$ com maior frequência acumulada.
  - **Critério de desempate:** em caso de contagens idênticas entre dois ou mais bins, seleciona-se estritamente o bin de **menor índice binário** $\text{idx}$.
- Representação RGB de 8 bits da cor dominante (`dominant_rgb`):
  Expandido para o intervalo $[0, 255]$ multiplicando por $17$ ($0xF \cdot 17 = 255$):
  $$R_{\text{dom}} = R_4 \cdot 17, \quad G_{\text{dom}} = G_4 \cdot 17, \quad B_{\text{dom}} = B_4 \cdot 17$$
- Cor média (`mean_rgb`): média aritmética de cada canal sobre os $N = W \cdot H$ pixels:
  $$[\bar{R}, \bar{G}, \bar{B}] = \left[\frac{1}{N}\sum R, \frac{1}{N}\sum G, \frac{1}{N}\sum B\right]$$

### 4.6 Hash Perceptual (`phash`)
O algoritmo pHash gera uma impressão digital perceptual de 64 bits (16 caracteres hexadecimais) imune a ruído de alta frequência:

1. **Redimensionamento para $32 \times 32$ por Média de Área:**
   - O canal $Y$ da imagem original $W \times H$ é projetado sobre uma grade de $32 \times 32$ células.
   - Para cada célula destino $(u, v)$ onde $u, v \in [0, 31]$:
     - Limites horizontais contínuos: $x_0 = u \cdot \frac{W}{32}, \quad x_1 = (u + 1) \cdot \frac{W}{32}$.
     - Limites verticais contínuos: $y_0 = v \cdot \frac{H}{32}, \quad y_1 = (v + 1) \cdot \frac{H}{32}$.
     - O valor da célula $I(u, v)$ é a integral da luminância $Y(x, y)$ ponderada pela área de intersecção com cada pixel original:
       $$I(u, v) = \frac{\sum_{y, x} Y(x, y) \cdot \text{overlap\_x}(x) \cdot \text{overlap\_y}(y)}{(W / 32) \cdot (H / 32)}$$
       onde:
       $$\text{overlap\_x}(x) = \max(0.0, \min(x + 1.0, x_1) - \max(x \cdot 1.0, x_0))$$
       $$\text{overlap\_y}(y) = \max(0.0, \min(y + 1.0, y_1) - \max(y \cdot 1.0, y_0))$$
   - Quando $W$ e $H$ são múltiplos inteiros de 32 (ex: 64, 128, 256), a média de área simplifica-se exatamente para a média aritmética dos blocos de tamanho $(W/32) \times (H/32)$.

2. **Transformada Discreta de Cosseno 2D (DCT-II):**
   - Para $u, v \in [0, 7]$ (apenas a submatriz $8 \times 8$ de baixas frequências é calculada):
     $$D(u, v) = \sum_{y=0}^{31} \sum_{x=0}^{31} I(u, v) \cos\left(\frac{\pi (2x + 1) u}{64}\right) \cos\left(\frac{\pi (2y + 1) v}{64}\right)$$
   - *Estabilidade Numérica:* Resíduos de ponto flutuante com magnitude $|D(u, v)| < 10^{-6}$ decorrentes de somas trigonométricas finitas devem ser truncados para $0.0$.

3. **Exclusão do Componente DC $(0, 0)$:**
   - O termo $D(0, 0)$ representa a média geral de brilho da imagem e não contém informação estrutural de frequência.
   - Define-se a matriz de coeficientes $C(u, v)$:
     $$C(0, 0) = 0.0, \quad C(u, v) = D(u, v) \text{ para } (u, v) \ne (0, 0)$$

4. **Cálculo da Mediana:**
   - Os 64 coeficientes $C(u, v)$ são ordenados em ordem não-decrescente: $S_0 \le S_1 \le \dots \le S_{63}$.
   - A mediana é definida como:
     $$\text{median} = \frac{S_{31} + S_{32}}{2.0}$$

5. **Construção do Hash de 64 Bits:**
   - Para cada posição em ordem row-major ($k = 8 \cdot v + u$ para $v \in [0, 7], u \in [0, 7]$):
     $$\text{bit}_k = \begin{cases} 1, & \text{se } C(u, v) > \text{median} \\ 0, & \text{caso contrário} \end{cases}$$
   - O valor de 64 bits é montado com o bit $k=0$ na posição mais significativa (MSB):
     $$\text{hash} = \sum_{k=0}^{63} \text{bit}_k \cdot 2^{63 - k}$$
   - O resultado é codificado em hexadecimal minúsculo com exatamente 16 dígitos: `"{:016x}"`.

---

## 5. Métricas de Ponto Flutuante

Estas métricas envolvem operações em precisão dupla (float64) e possuem tolerâncias $\epsilon$ especificadas para validação cruzada.

### 5.1 Luminância Média (`mean_y`)
$$\mu_Y = \frac{1}{N} \sum_{i=1}^N Y_i$$
- **Tolerância:** $\epsilon = 10^{-4}$.

### 5.2 Entropia de Shannon de Y (`entropy_y`)
Avalia a incerteza e riqueza de distribuição de luminância da imagem:
- Histograma com 256 bins ($k \in [0, 255]$).
- Probabilidade empírica: $p_k = \frac{\text{count}(Y = k)}{N}$.
- Entropia em bits por pixel:
  $$H(Y) = -\sum_{k=0, p_k > 0}^{255} p_k \log_2(p_k)$$
- Imagem de cor sólida: $H(Y) = 0.0$.
- **Tolerância:** $\epsilon = 10^{-4}$.

### 5.3 Entropia do Resíduo Horizontal de Y (`entropy_residual_y`)
Mede a redundância preditiva horizontal (DPCM), indicativo direto da compressibilidade sem perdas:
- Diferença horizontal para $y \in [0, H-1]$ e $x \in [1, W-1]$:
  $$\Delta Y(x, y) = Y(x, y) - Y(x-1, y)$$
- Total de amostras: $N_\Delta = (W - 1) \cdot H$. Se $W \le 1$, $H(\Delta Y) = 0.0$.
- O resíduo assume 511 valores possíveis: $\Delta Y \in [-255, 255]$.
- Histograma centrado em 0: $p_d = \frac{\text{count}(\Delta Y = d)}{N_\Delta}$.
- Entropia em bits por pixel:
  $$H(\Delta Y) = -\sum_{d, p_d > 0} p_d \log_2(p_d)$$
- Imagem de cor sólida: todos os resíduos são $0 \implies p_0 = 1.0 \implies H(\Delta Y) = 0.0$.
- **Tolerância:** $\epsilon = 10^{-4}$.

### 5.4 Informação Espacial (`spatial_information` / SI)
Conforme norma **ITU-T P.910**, mede a energia e desvio das bordas de alta frequência:
- Aplicada exclusivamente sobre o interior da imagem ($x \in [1, W-2], y \in [1, H-2]$), descartando a borda de 1 pixel. Total de pixels válidos: $N_{\text{valid}} = (W - 2)(H - 2)$. Se $W \le 2$ ou $H \le 2$, $\text{SI} = 0.0$.
- Filtros de Sobel 2D:
  $$G_x(x, y) = [Y(x+1, y-1) + 2Y(x+1, y) + Y(x+1, y+1)] - [Y(x-1, y-1) + 2Y(x-1, y) + Y(x-1, y+1)]$$
  $$G_y(x, y) = [Y(x-1, y+1) + 2Y(x, y+1) + Y(x+1, y+1)] - [Y(x-1, y-1) + 2Y(x, y-1) + Y(x+1, y-1)]$$
- Magnitude de Sobel:
  $$M(x, y) = \sqrt{G_x(x, y)^2 + G_y(x, y)^2}$$
- Desvio padrão populacional:
  $$\mu_M = \frac{1}{N_{\text{valid}}} \sum M(x, y)$$
  $$\text{SI} = \sigma_M = \sqrt{\frac{1}{N_{\text{valid}}} \sum (M(x, y) - \mu_M)^2}$$
- **Tolerância:** $\epsilon = 10^{-3}$.

### 5.5 Energia de Gradiente (`gradient_energy`)
Média da soma dos quadrados dos gradientes de Sobel na região interior:
$$\text{GE}_Y = \frac{1}{N_{\text{valid}}} \sum_{x=1}^{W-2} \sum_{y=1}^{H-2} [G_x(x, y)^2 + G_y(x, y)^2]$$
- **Tolerância:** $\epsilon = 10^{-3}$.

### 5.6 Variância Laplaciana (`laplacian_variance`)
Métrica canônica de foco e nitidez baseada no stencil isotrópico de 4 vizinhos:
$$L(x, y) = Y(x+1, y) + Y(x-1, y) + Y(x, y+1) + Y(x, y-1) - 4 \cdot Y(x, y)$$
- Calculada no interior $x \in [1, W-2], y \in [1, H-2]$.
- Média e variância populacional:
  $$\mu_L = \frac{1}{N_{\text{valid}}} \sum L(x, y)$$
  $$\operatorname{Var}(L) = \frac{1}{N_{\text{valid}}} \sum (L(x, y) - \mu_L)^2$$
- Imagem sólida: $L(x, y) = 0 \implies \operatorname{Var}(L) = 0.0$.
- **Tolerância:** $\epsilon = 10^{-3}$.

### 5.7 Variância de Cor (`color_variance`)
Variância amostral populacional para cada canal RGB sobre toda a imagem ($N = W \cdot H$):
$$\operatorname{Var}(C) = \frac{1}{N} \sum_{i=1}^N (C_i - \mu_C)^2 \quad \text{para } C \in \{R, G, B\}$$
$$\operatorname{Var}_{\text{sum}} = \operatorname{Var}(R) + \operatorname{Var}(G) + \operatorname{Var}(B)$$
- **Tolerância:** $\epsilon = 10^{-3}$.

### 5.8 Métricas de Canal Alpha (`alpha`)
- `has_alpha`: booleano (`true` se `DEPTH == 4`, `false` se `DEPTH == 3`).
- Se `has_alpha == false`:
  - `sparsity` = $0.0$.
  - `binarity` = $1.0$ (todos os pixels são opacos).
- Se `has_alpha == true`:
  - `sparsity`: Fração de pixels totalmente transparentes ($A = 0$):
    $$\text{sparsity} = \frac{\operatorname{count}(A == 0)}{N}$$
  - `binarity`: Fração de pixels binários ($A \in \{0, 255\}$):
    $$\text{binarity} = \frac{\operatorname{count}(A == 0 \lor A == 255)}{N}$$
- **Tolerância:** $\epsilon = 10^{-4}$.

### 5.9 Adequação a 4:2:0 (`adequacy_420`)
Determina a suscetibilidade da imagem a artefatos de compressão por subamostragem de croma:

1. **Energia de Gradiente de Croma:**
   - Calcula-se a energia de gradiente de Sobel nos planos $Cb$ e $Cr$ na mesma região interior que $Y$:
     $$\text{GE}_{Cb} = \frac{1}{N_{\text{valid}}} \sum (G_{x,Cb}^2 + G_{y,Cb}^2), \quad \text{GE}_{Cr} = \frac{1}{N_{\text{valid}}} \sum (G_{x,Cr}^2 + G_{y,Cr}^2)$$
     $$\text{GE}_{\text{chroma}} = \text{GE}_{Cb} + \text{GE}_{Cr}$$
   - Razão de energia de gradiente:
     $$\text{chroma\_gradient\_ratio} = \begin{cases} \frac{\text{GE}_{\text{chroma}}}{\text{GE}_Y}, & \text{se } \text{GE}_Y > 0 \\ 0.0, & \text{caso contrário} \end{cases}$$

2. **Erro Quadrático Médio (MSE) de Ida e Volta 2x2:**
   - Simula a subamostragem 4:2:0 dividindo a imagem em blocos disjuntos de $2 \times 2$ pixels.
   - Para cada bloco $B$, calcula-se a média aritmética $\bar{c} = \frac{1}{|B|}\sum_{p \in B} c_p$.
   - A reconstrução substitui cada pixel do bloco por $\bar{c}$.
   - O MSE por canal é:
     $$\text{MSE}_c = \frac{1}{N} \sum_{i=1}^N (c_i - \bar{c}_{\text{bloco}(i)})^2 \quad \text{para } c \in \{Cb, Cr\}$$
     $$\text{MSE}_{\text{chroma}} = \frac{1}{2}(\text{MSE}_{Cb} + \text{MSE}_{Cr})$$
- **Tolerância:** $\epsilon = 10^{-3}$.

### 5.10 Fração de Área Plana (`flat_area`)
Mede a proporção da imagem dominada por regiões visualmente planas (onde artefatos de bloco JPEG e bandas de quantização são mais perceptíveis):
- A imagem é particionada em blocos disjuntos de $8 \times 8$ pixels.
- Apenas blocos completos são avaliados ($b_x \in [0, \lfloor W/8 \rfloor - 1], b_y \in [0, \lfloor H/8 \rfloor - 1]$).
- Total de blocos completos: $M_8 = \lfloor W/8 \rfloor \cdot \lfloor H/8 \rfloor$. Se $M_8 = 0$, $\text{flat\_area} = 1.0$.
- Para cada bloco de 64 pixels, calcula-se a variância de luminância $\operatorname{Var}_b(Y)$:
  $$\mu_b = \frac{1}{64} \sum_{i=1}^{64} Y_i, \quad \operatorname{Var}_b = \frac{1}{64} \sum_{i=1}^{64} (Y_i - \mu_b)^2$$
- Um bloco é considerado "plano" se $\operatorname{Var}_b < 16.0$ (desvio padrão $\sigma_b < 4.0$).
- $\text{flat\_area}$ é a razão entre o número de blocos planos e $M_8$:
  $$\text{flat\_area} = \frac{\operatorname{count}(\operatorname{Var}_b < 16.0)}{M_8}$$
- **Tolerância:** $\epsilon = 10^{-4}$.

### 5.11 BlurHash Oficial Wolt (`blurhash`)
Implementação estrita da especificação oficial Wolt BlurHash:
- Componentes fixados na arena: $n_x = 4, n_y = 3$.
- Alfabeto Base83 (83 caracteres):
  `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%*+,-.:;=?@[]^_{|}~`
- **Passo 1 — Conversão sRGB $\to$ Linear:**
  $$v = c / 255.0$$
  $$\text{linear}(v) = \begin{cases} \frac{v}{12.92}, & \text{se } v \le 0.04045 \\ \left(\frac{v + 0.055}{1.055}\right)^{2.4}, & \text{se } v > 0.04045 \end{cases}$$
- **Passo 2 — Projeção sobre Funções de Base:**
  Para $y_{\text{comp}} \in [0, 2]$ e $x_{\text{comp}} \in [0, 3]$:
  $$\text{norm} = \begin{cases} 1.0, & \text{se } x_{\text{comp}} = 0 \text{ e } y_{\text{comp}} = 0 \\ 2.0, & \text{caso contrário} \end{cases}$$
  $$\text{fator}(x_{\text{comp}}, y_{\text{comp}}) = \frac{\text{norm}}{W \cdot H} \sum_{y=0}^{H-1} \sum_{x=0}^{W-1} \text{linear}(P(x, y)) \cos\left(\frac{\pi x_{\text{comp}} x}{W}\right) \cos\left(\frac{\pi y_{\text{comp}} y}{H}\right)$$
- **Passo 3 — Codificação DC:**
  O componente $(0, 0)$ é convertido de volta para sRGB inteiro:
  $$c_{\text{srgb}} = \begin{cases} \lfloor v \cdot 12.92 \cdot 255 + 0.5 \rfloor, & \text{se } v \le 0.0031308 \\ \lfloor (1.055 \cdot v^{1/2.4} - 0.055) \cdot 255 + 0.5 \rfloor, & \text{se } v > 0.0031308 \end{cases}$$
  onde $v = \max(0, \min(1, \text{fator}(0, 0)))$.
  O valor 24 bits $(R \ll 16) | (G \ll 8) | B$ é codificado em 4 dígitos Base83.
- **Passo 4 — Codificação AC:**
  Os 11 componentes AC restantes ($4 \cdot 3 - 1 = 11$) são quantizados recursivamente com escala baseada no valor máximo absoluto e codificados em 2 dígitos Base83 cada.
- Comprimento final da string: $1 \text{ (tamanho)} + 1 \text{ (max AC)} + 4 \text{ (DC)} + 11 \cdot 2 = 28$ caracteres.

---

## 6. Esquema do Payload JSON de Resposta

O endpoint `POST /run?op=analyze` e o binário batch devolvem o JSON estruturado:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ArenaAnalyzeResult",
  "type": "object",
  "required": [
    "width",
    "height",
    "aspect_ratio",
    "block_alignment",
    "mean_y",
    "entropy_y",
    "entropy_residual_y",
    "spatial_information",
    "gradient_energy",
    "laplacian_variance",
    "color_variance",
    "unique_colors",
    "alpha",
    "adequacy_420",
    "flat_area",
    "dominant_color",
    "phash",
    "blurhash"
  ],
  "properties": {
    "width": { "type": "integer", "minimum": 1 },
    "height": { "type": "integer", "minimum": 1 },
    "aspect_ratio": {
      "type": "object",
      "required": ["str", "float"],
      "properties": {
        "str": { "type": "string" },
        "float": { "type": "number" }
      }
    },
    "block_alignment": {
      "type": "object",
      "required": ["b8", "b16", "b64", "b256"],
      "properties": {
        "b8": { "$ref": "#/definitions/BlockInfo" },
        "b16": { "$ref": "#/definitions/BlockInfo" },
        "b64": { "$ref": "#/definitions/BlockInfo" },
        "b256": { "$ref": "#/definitions/BlockInfo" }
      }
    },
    "mean_y": { "type": "number" },
    "entropy_y": { "type": "number" },
    "entropy_residual_y": { "type": "number" },
    "spatial_information": { "type": "number" },
    "gradient_energy": { "type": "number" },
    "laplacian_variance": { "type": "number" },
    "color_variance": {
      "type": "object",
      "required": ["var_r", "var_g", "var_b", "var_sum"],
      "properties": {
        "var_r": { "type": "number" },
        "var_g": { "type": "number" },
        "var_b": { "type": "number" },
        "var_sum": { "type": "number" }
      }
    },
    "unique_colors": { "type": "integer", "minimum": 1 },
    "alpha": {
      "type": "object",
      "required": ["has_alpha", "sparsity", "binarity"],
      "properties": {
        "has_alpha": { "type": "boolean" },
        "sparsity": { "type": "number" },
        "binarity": { "type": "number" }
      }
    },
    "adequacy_420": {
      "type": "object",
      "required": ["chroma_gradient_energy", "chroma_gradient_ratio", "mse_cb", "mse_cr", "mse_chroma"],
      "properties": {
        "chroma_gradient_energy": { "type": "number" },
        "chroma_gradient_ratio": { "type": "number" },
        "mse_cb": { "type": "number" },
        "mse_cr": { "type": "number" },
        "mse_chroma": { "type": "number" }
      }
    },
    "flat_area": { "type": "number" },
    "dominant_color": {
      "type": "object",
      "required": ["dominant_rgb", "dominant_bin", "mean_rgb"],
      "properties": {
        "dominant_rgb": { "type": "array", "items": { "type": "integer" }, "minItems": 3, "maxItems": 3 },
        "dominant_bin": { "type": "integer" },
        "mean_rgb": { "type": "array", "items": { "type": "number" }, "minItems": 3, "maxItems": 3 }
      }
    },
    "phash": { "type": "string", "pattern": "^[0-9a-f]{16}$" },
    "blurhash": { "type": "string", "minLength": 28, "maxLength": 28 }
  },
  "definitions": {
    "BlockInfo": {
      "type": "object",
      "required": ["w_mod", "h_mod", "partial_pixels", "partial_pct"],
      "properties": {
        "w_mod": { "type": "integer" },
        "h_mod": { "type": "integer" },
        "partial_pixels": { "type": "integer" },
        "partial_pct": { "type": "number" }
      }
    }
  }
}
```

---

## 7. Casos de Teste Sintéticos e Gabarito Analítico

As 8 fixtures sintéticas geradas pelo harness servem como teste de conformidade de regressão com resultados esperados rigorosamente conhecidos:

| Fixture | Dimensões | Formato | Propriedades Matemáticas Notáveis |
|---|---|---|---|
| `solid_red.pam` | $64 \times 64$ | RGB | $Y=77, Cb=85, Cr=255$. Entropias = 0, SI = 0, GE = 0, Lap = 0. Cores únicas = 1. pHash = `0000000000000000`. Flat area = 1.0. |
| `solid_black.pam` | $64 \times 64$ | RGB | $Y=0, Cb=128, Cr=128$. Entropias = 0, SI = 0, GE = 0. pHash = `0000000000000000`. BlurHash = `L00000fQfQfQfQfQfQfQfQfQfQfQ`. |
| `checkerboard_1x1.pam` | $64 \times 64$ | RGB | Alternância pixel a pixel (0 e 255). Sobel $G_x = G_y = 0 \implies \text{SI} = 0, \text{GE} = 0$. Laplaciano máximo $\operatorname{Var}(L) = 1.040.400$. Entropias = 1.0. Flat area = 0.0. |
| `checkerboard_8x8.pam` | $64 \times 64$ | RGB | Blocos $8 \times 8$ sólidos. Bordas de bloco capturadas pelo Sobel e Laplaciano. Cada bloco é 100% uniforme internamente $\implies \text{flat\_area} = 1.0$. pHash simétrico `0055005500550055`. |
| `gradient_h.pam` | $64 \times 64$ | RGB | $R=G=B=x \cdot 255 / 63$. $G_y = 0$, $G_x > 0$. Entropia de resíduo horizontal baixa/regular. |
| `gradient_v.pam` | $64 \times 64$ | RGB | $R=G=B=y \cdot 255 / 63$. $G_x = 0$, $G_y > 0$. Resíduo horizontal $\Delta Y = 0$ em cada linha $\implies H(\Delta Y) = 0.0$. |
| `noise_deterministic.pam` | $64 \times 64$ | RGB | Ruído pseudoaleatório determinístico gerado com semente fixa 42. Máxima entropia e riqueza espectral. |
| `alpha_boxes.pam` | $64 \times 64$ | RGB_ALPHA | 4 quadrantes com diferentes níveis de transparência ($A = 0, 85, 170, 255$). Valida `has_alpha = true`, `sparsity = 0.25`, `binarity = 0.5`. |
