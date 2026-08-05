# Brand Guidelines: BGC Liquidez

Este documento serve como guia base para a interface web do relatório "Highlights Crédito Privado", inspirado na identidade corporativa do **BGC Group** e da **BGC Liquidez**. O objetivo é entregar uma interface que transborde excelência, confiança institucional e vanguarda tecnológica.

## 1. Princípios de Design (Estética Premium)
O mercado de balcão e de Crédito Privado exige extrema precisão. Portanto, o relatório deve ser:
*   **Clean (Limpo):** Foco absoluto na clareza dos dados e números. Reduzir o ruído visual (excesso de bordas, cores vibrantes desnecessárias).
*   **Sophisticated (Sofisticado):** Uso de espaços em branco (whitespace) generosos para criar respiro, sombras suaves para profundidade e gradientes sutis para um toque moderno.
*   **Dynamic (Dinâmico):** Na versão web, incluir micro-animações, como linhas de tabela sendo sutilmente realçadas ao passar o mouse (`hover`), melhorando o engajamento e a fluidez de leitura.

## 2. Paleta de Cores

As cores refletem a solidez do BGC Group, ancoradas no Azul Corporativo clássico, temperadas com tons neutros para suportar dados e alertas para variações financeiras.

| Nome da Cor | Código HEX | Aplicação Recomendada |
| :--- | :--- | :--- |
| **BGC Corporate Blue** | `#0033A0` | Cor primária. Elementos de branding (logo), cabeçalhos principais, gráficos de destaque. |
| **BGC Light Blue** | `#0072CE` | Cor secundária. Elementos interativos, subtítulos, links e highlights menores. |
| **Navy Text** | `#001A4D` | Texto principal. Uma alternativa muito mais elegante e moderna ao preto absoluto (`#000000`). |
| **Surface White** | `#FFFFFF` | Cor de fundo principal do relatório. Garante legibilidade em e-mails e telas brilhantes. |
| **Soft Platinum (Cinza)** | `#F4F5F7` | Fundo para os 'Cards' de resumo de mercado ou para zebrar tabelas financeiras longas. |
| **Positive Green** | `#0B8A44` | Uso estrito para indicadores financeiros em alta ou spreads que comprimiram (positivos). |
| **Negative Red** | `#D32F2F` | Uso estrito para quedas e aberturas de taxas/spreads. |

## 3. Tipografia

Para relatórios financeiros, a leitura rápida de grandes blocos de números é crítica. As fontes selecionadas no Google Fonts garantem que numerais sejam mono-espaçados e claros.

*   **Títulos e Destaques (Headers):** `Montserrat` ou `Outfit`.
    *   Trazem um peso institucional e geométrico, excelente para o título "Highlights Crédito Privado" e números muito grandes.
*   **Corpo de Texto e Tabelas (Body):** `Inter` ou `Roboto`.
    *   Desenhadas especificamente para legibilidade em telas de computador e interfaces de dados. Ótima distinção entre o `0` (zero) e a letra `O`.

## 4. Estilos de Componentes (UI/UX)

### Tabelas (Crédito Privado)
*   **Alinhamento:** Todo texto descritivo (Emissor, Indexador) é alinhado à esquerda. Todo dado financeiro (Taxa, Prazo, Volume, Rating) é alinhado à direita.
*   **Bordas:** Remover bordas verticais. Usar apenas bordas horizontais muito finas e em tom cinza claro (`#E5E7EB`) para separar as linhas.
*   **Cabeçalho da Tabela:** Fundo branco com tipografia em `Navy Text` em negrito, ou fundo cinza claro (`Soft Platinum`) com texto em `Corporate Blue`.

### Sombras e Profundidade (Cards)
Para destacar os "Highlights" do dia acima da tabela geral:
*   Utilizar fundos brancos sobre um fundo principal levemente cinza (ou vice-versa), adicionando uma sombra elegante: `box-shadow: 0 4px 20px rgba(0, 51, 160, 0.08)`. Isso trará o elemento para "frente" na tela sem ser agressivo.

## 5. CSS Tokens - Ponto de Partida

Ao iniciar a folha de estilo `index.css`, comece importando estas variáveis raízes:

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Montserrat:wght@600;700&display=swap');

:root {
  /* Colors */
  --bgc-blue: #0033A0;
  --bgc-light-blue: #0072CE;
  --text-navy: #001A4D;
  --text-muted: #6B7280;
  --bg-surface: #FFFFFF;
  --bg-platinum: #F4F5F7;
  --market-up: #0B8A44;
  --market-down: #D32F2F;
  --border-color: #E5E7EB;
  
  /* Typography */
  --font-body: 'Inter', sans-serif;
  --font-heading: 'Montserrat', sans-serif;
}
```
