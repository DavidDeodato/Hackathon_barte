# Percurso de demonstração do Lastro

Versão-base do produto: `0cc8d32`. Os slides 34–37 e 43 usam capturas reais da interface local, consultando os seis CSVs publicados com hashes conferidos. Não são mockups de tela. Essa consulta não constitui uma nova execução financeira, uma chamada ao modelo nem aprovação de Helena.

## Ensaio principal: 3 minutos

| Tempo | Ação da analista | Evidência a apontar | Avanço |
|---|---|---|---|
| 0:00–0:25 | Abrir **Fechamento** e selecionar setembro | Execução `close-2068e24a102ebea3`, estado de revisão, comissões e seis arquivos | 34 |
| 0:25–1:10 | **Pendências**, abrir diferença Orbe de R$ 1.546,28 e **Conferir rastro desta saída** | 87 componentes; `TX88423647`, R$ 66,28, linha 749 da Orbe. Conferir as taxas mostradas no avanço 20 | 35 |
| 1:10–2:10 | **Investigação**, **Escolher caso para revisão**, **Rota** | Valor líquido, destino Orbe, responsável Helena e evidências que faltam para encerrar | 36 |
| 2:10–3:00 | Voltar a **Pendências**, abrir **Contrato · Atlas** | Volume bruto conhecido, comissão desconhecida e Comercial + Helena como responsáveis. O sistema preserva as origens sem inventar taxa | 37 |

Na mesa, **Conferir documentos** e **Executar revisão** exercitam o modo documental. O estado esperado é preparação para revisão humana, sem aprovação. Esse modo não executa investigador e crítico como modelos. Para apresentar inferência real, selecionar **Investigar com IA**, usar um servidor com credenciais válidas, abrir as fontes retornadas e apontar o estado efetivo. Não usar uma captura documental como prova de IA executada.

## Continuidade de outubro: 40 segundos

Em **Documentos**, clicar **Novo conjunto**, informar nome e competência `2026-10`, criar o conjunto e mostrar **Escolher arquivos**, os papéis dos documentos e **Processar seleção**. Sem documentos, o botão fica indisponível e não existem resultados de outubro. A captura do avanço 43 mostra exatamente esse estado.

Os avanços 44–45 mostram a orientação operacional: confirmar a taxa Atlas válida desde 10/09 para faturar setembro junto com outubro e conferir o crédito da transferência de R$ 300 mil em 01/10. O lote real de outubro e a resolução automática entre competências ainda não foram demonstrados. Não apresentar a simples criação do conjunto como fechamento concluído.

## Preparação do ambiente

O modo completo requer os sete originais, incluindo `06_orbe_ajustes_tardios_set2026.csv`, preservados sem limpeza manual. Seguir o README do produto para processar o lote real, selecionar a execução e configurar o modelo no servidor. Conferir versão, competência, arquivos selecionados e hashes antes do ensaio. Chaves e senhas não entram no deck nem no Git.

Para conferir a interface sem reprocessar os insumos, o helper abaixo importa uma **consulta arquivada às saídas publicadas**, em estado local novo. Ele valida os hashes dos CSVs e o relatório do rastro, preserva a identidade e o horário da execução do manifesto e não cria eventos fictícios de cálculo. As decisões permanecem pendentes. Usa a API e a interface do produto, sem transportes de IA simulados.

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python tools/apresentacao/serve_published_demo.py --state-dir /tmp/lastro-pitch-consulta --port 8000
```

Em outro terminal:

```bash
cd web
npm ci
npm run dev
```

Abrir `http://127.0.0.1:5173`. O diretório de estado deve ser novo; o helper recusa sobrescrever um ledger existente. No Windows, substituir `.venv/bin/python` por `.venv/Scripts/python.exe`. Se as portas estiverem ocupadas, usar portas livres e configurar o proxy Vite e `--frontend-origin` para a mesma origem local. O helper só escuta em loopback.

As capturas desta versão usaram API em `127.0.0.1:8017`, frontend em `127.0.0.1:5177`, estado isolado e os arquivos de `saida/` byteidênticos aos publicados. Foram conferidos o acesso, a navegação, o rastro da Rota, a mesa do caso, a consulta documental e o conjunto vazio de outubro. Não houve processamento novo dos sete originais nem inferência paga nesta revisão.

## Se a demo falhar

- **Rede ou autenticação:** continuar com as capturas identificadas e os CSVs publicados. Dizer que está mostrando uma consulta arquivada.
- **Modelo indisponível, erro ou limite atingido:** mostrar o estado observado e continuar por **Conferir documentos**. Não afirmar que os agentes concluíram a investigação.
- **Fonte ausente:** mostrar a referência e a pendência. Um pacote que exige evidência não comprova que ela foi recebida.
- **Regra não confirmada:** usar Atlas para explicar o bloqueio do faturamento da taxa e a responsabilidade do Comercial.

## Ritmo para 15 minutos

| Bloco | Tempo de ensaio |
|---|---:|
| 0–10: cliente e problema | 1min45 |
| 11–20: solução, apuração e origem | 2min15 |
| 21–25: arquitetura e decisão humana | 1min30 |
| 26–33: valores financeiros e conferência | 1min45 |
| 34–37: demo principal | 3min |
| 38–42: correção da IA, pergunta e premissa | 1min45 |
| 43–45: outubro e limites | 1min15 |
| 46–49: plano e encerramento | 1min |
| Margem para transições | 45s |

Os slides são avanços da fala, com um tópico por avanço. As metas de tempo são para ensaio e não configuram transições automáticas. Reservar os cinco minutos de perguntas para fonte, soma, regra, limite e responsabilidade. Não prometer economia de tempo que ainda não foi medida.

## Evidências de avaliação

| Critério | Evidência desta versão | Limite |
|---|---|---|
| Causa raiz | Fontes, vigência, contexto de Helena e comunicação da isenção Casa | Reduzir tarefas não elimina espera por parceiro ou decisão comercial |
| Hipóteses | Tolerância de remessas escrita no avanço 42, separada da resposta confirmada da Casa | Tolerância é escolha do time |
| Perguntar | Pergunta de David, resposta de Helena às 13h34 e confronto com AN88445172 | Transcrição fornecida pela participante, sem nova consulta ao Slack |
| Comunicação | Avanços para o financeiro, um tópico por avanço e demo até a origem | Cronometrar em ensaio |
| Uso de IA | Proposta genérica rejeitada, investigação dirigida e distinção entre modo documental e inferência | Não comprova ganho semântico do crítico |
| Números | Saídas, hashes, somas, rastro e ajustes tardios | Consistência interna não substitui o gabarito |
| Pontualidade | Código, slides e artefatos estão versionados | Envio no canal, checkpoints e horário exigem seus próprios comprovantes; não foram inventados |

## Arquivos de apoio

- `slides/assets/evidencias-setembro.json`: números e hashes usados nos avanços.
- `slides/assets/demo/`: capturas reais, preservadas sem edição raster.
- [Pergunta de David](../../contexto/PERGUNTA_DAVID_CASA.md): pergunta, resposta e alcance da confirmação.
- `PROMPTS/SESSAO_001.md` e conversa pública `rollout-2026-10-17T13-11-21-01a14aa1-d2e6-7c10-8f4d-76777ec9e274.jsonl`: registros da direção da IA, sobretudo as linhas 17, 20 e 37.
