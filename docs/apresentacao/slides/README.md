# Abertura do pitch Lastro

Primeira versão visual para revisar a direção da apresentação: dez slides, correspondentes aos avanços 0 a 9 do [roteiro](../roteiro.md). O material cobre a capa e o problema. A continuação da solução e da arquitetura permanece no roteiro, para desenvolvimento depois da revisão desta abertura.

![Visão geral dos dez slides](previews/overview.png)

## Sequência

| Avanço | Prévia | Conteúdo |
|---|---|---|
| 0 | [Capa](previews/00.png) | Marca Lastro e fechamento financeiro da Tarvo |
| 1 | [Tarvo](previews/01.png) | Identificação tipográfica provisória do cliente |
| 2 | [Três frentes](previews/02.png) | Posições das fontes ainda sem conexão |
| 3 | [Planilha](previews/03.png) | Taxas e condições de cada lojista |
| 4 | [Relatórios e extratos](previews/04.png) | Cobranças e movimentos registrados |
| 5 | [Helena](previews/05.png) | Triângulo completo, com Helena no centro associada ao marcador 3 |
| 6 | [Quanto pode faturar](previews/06.png) | Junção das informações no fechamento |
| 7 | [O que precisa corrigir](previews/07.png) | Segunda pergunta acrescentada à primeira |
| 8 | [Valores pendentes](previews/08.png) | Terceira pergunta acrescentada às anteriores |
| 9 | [Consequências](previews/09.png) | Oito dias úteis, cobranças incorretas e dependência das regras tácitas |

## Composição

Canvas 1280 × 720, proporção 16:9. Fundo claro e verde vêm dos tokens do Lastro; capa e consequências usam o verde escuro. A tipografia é Arial. Os diagramas, textos e conectores são objetos nativos editáveis da apresentação. A marca Lastro é o SVG original do repositório, com proporção preservada.

Os slides são estados sucessivos da composição. Há um avanço para cada frente e para cada pergunta, com destaque no assunto novo. Esta versão não configura animação automática entre posições.

**Asset pendente:** a identificação “Tarvo” é texto provisório. Substituir pela logo confirmada, preservando sua posição entre os avanços 1 e 2. Helena aparece pelo nome, sem retrato atribuído a uma pessoa real.

O prazo de oito dias úteis descreve o processo relatado no case. A sequência ainda não apresenta resultado ou economia alcançada pelo Lastro. As fontes do relato e a fala correspondente acompanham as notas dos slides.

## Fonte editável e reprodução

[abertura.mjs](abertura.mjs) exporta o callback `buildOpening`, usado em uma sessão de apresentação já conectada. O código recebe `presentation` e `input`; não cria outro documento. Para gerar a mesma abertura em uma apresentação vazia:

1. Executar o callback com `input.phase = 'cover'` e `input.logoPath` apontando para `web/public/brand/lastro-logo-inverse.svg` no checkout utilizado.
2. Aguardar a conclusão da capa. Executar com `input.phase = 'develop'` e `input.indices = [1, 2, 3, 4]`.
3. Aguardar a conclusão. Executar com `input.phase = 'develop'` e `input.indices = [5, 6, 7, 8, 9]`.
4. Renderizar e conferir os dez slides. Usar a mesma sessão para corrigir o documento existente.

O callback preserva slides que já tenham formas e não os sobrescreve ao repetir um lote. `refineIntro` registra o ajuste aplicado aos slides 1 e 2 da primeira versão, usando os IDs retornados pela inspeção; a construção inicial já inclui essa composição ajustada.

As imagens em `previews/` são capturas renderizadas da apresentação editável. Servem à revisão visual no repositório e precisam ser atualizadas quando o documento mudar.
