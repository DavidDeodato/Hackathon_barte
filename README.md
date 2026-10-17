# Lastro — fechamento Tarvo

Preparar o fechamento de setembro de 2026 com origem por numero, pendencias explicitas e investigacao das regras aplicaveis. O motor financeiro e deterministico; a camada de investigacao distingue consulta local, inferencia real e replay de teste. Propostas nao aprovam regras nem emitem notas fiscais.

## Estado verificavel

Os arquivos recebidos, incluindo os 14 ajustes tardios, foram processados nos seis CSVs de `saida/`. A revisao independente conferiu cada evento adicional, seus vinculos e taxas, a conservacao dos valores e os rastros. Os nove estornos de vendas anteriores a setembro foram conferidos contra a vigencia da tabela fornecida; a ausencia das vendas brutas de agosto nao equivale a falta dessas taxas. As notas sao propostas para revisao, nao documentos fiscais emitidos.

O arquivo `06_orbe_ajustes_tardios_set2026.csv` foi incorporado na execucao `close-2068e24a102ebea3`. Os ajustes reduzem a comissao de checkout e as notas propostas em R$ 3.304,39; remessas, classificacoes bancarias e divergencias de taxa permanecem iguais. Consulte [atualizacoes do case](contexto/ATUALIZACOES_CASE.md).

| Resultado de setembro/2026 | Valor ou quantidade |
| --- | ---: |
| Comissao de checkout | R$ 203.735,34 |
| Comissao de remessas | R$ 39.543,45 |
| Notas propostas | R$ 243.284,29 em 21 notas |
| Movimentos bancarios classificados | 184 |
| Pendencias financeiras | 17 |
| Vinculos de rastreabilidade | 5.205 |

Os totais representam naturezas distintas e nao devem ser somados entre si. A comissao negativa de R$ 5,50 da Casa nao gera nota; a taxa da Atlas continua sem faturamento ate confirmacao comercial. A aprovacao financeira permanece com Helena.

## Executar do zero

Requer Python 3.14 e Node.js compativel com Vite 7 (22.12+ recomendado). A verificacao local usa Python 3.14 e Node 24. Obtenha o `Tarvo_Data_Pack_set2026.zip` fornecido pela organizacao e extraia os arquivos originais para `contexto/data_pack/`, sem limpeza manual. Acrescente nesse mesmo diretorio o arquivo original `06_orbe_ajustes_tardios_set2026.csv`, recebido separadamente. Os dados brutos sao ignorados pelo Git: um clone sozinho nao contem os insumos. O relatorio Ponte e lido do anexo do EML; preserve o arquivo completo. O pack nao esta embutido na imagem Docker canonica nem nas credenciais.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
$env:PYTHONPATH='src'
.venv/Scripts/python.exe -m tarvo.cli --input-dir contexto/data_pack --output-dir saida --period 2026-09
```

As seis saidas: `comissoes_por_lojista.csv`, `divergencias_taxa.csv`, `notas_a_emitir.csv`, `lancamentos_classificados.csv`, `pendencias.csv`, `rastro.csv`. Separador `;`, decimal com ponto, datas ISO. `manifest.json`, `detalhes.json` e `reconciliacao.json` complementam a verificacao das entradas e dos resultados.

O comando financeiro foi reexecutado em ambiente virtual novo no Windows/Python 3.14, com instalacao das dependencias sem cache e os sete originais explicitamente fornecidos. Os seis CSVs reproduzidos foram byteidenticos a `saida/`. Essa prova cobre o motor financeiro; a aplicacao e a integracao de IA possuem verificacoes separadas.

## Aplicacao local

Em um terminal, com `PYTHONPATH=src`:

```powershell
.venv/Scripts/python.exe -m uvicorn tarvo.api.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-proxy-headers
```

Em outro terminal:

```powershell
cd web
npm ci
npm run dev
```

Abra `http://127.0.0.1:5173`. A aplicacao conecta ao servidor pelo proxy local automaticamente. Nao execute dois servidores sobre o mesmo diretorio de estado. O acesso hospedado usa senha e sessao; a configuracao dos servicos pertence ao servidor. O frontend nunca recebe a chave do provedor de IA.

### Configuracao do servidor

As variaveis devem estar no ambiente do processo que inicia o servidor. `.env.example` documenta os nomes; a aplicacao nao carrega `.env` automaticamente.

| Variavel | Uso |
| --- | --- |
| `OPENAI_API_KEY` e `OPENAI_MODEL` | Consultas ao modelo no servidor. Modelo verificado: `gpt-4.1-mini`. O calculo financeiro funciona sem a chave; consultas ao modelo exigem acesso valido. |
| `TARVO_ACCESS_PASSWORD` | Senha da entrada pela interface. Configure no servidor hospedado. |
| `TARVO_API_TOKEN` | Credencial tecnica exigida quando `TARVO_ENV=production`; nao e solicitada ao usuario na interface. |
| `TARVO_STATE_DIR` | Diretorio persistente dos documentos, execucoes e conversas; no ambiente hospedado usa o volume `/data`. |
| `TARVO_INPUT_DIR` | Diretorio dos insumos locais, por padrao `contexto/data_pack/`. Novos conjuntos tambem podem ser enviados pela interface. |
| `TARVO_CORS_ORIGINS` | Origens explicitamente permitidas; o padrao local inclui as duas URLs da porta5173. |

Mantenha credenciais somente no ambiente privado. A publicacao atual usa Railway para interface, API e volume; Vercel, AWS e Cloudinary nao sao dependencias para reproduzir esse fluxo.

### Usar o assistente

Abra o botao Lastro no canto inferior direito. A conversa conserva a competencia, o conjunto e a execucao escolhidos, com historico persistido no servidor. Para mudar de contexto, crie uma nova conversa. As fontes da resposta abrem os resultados ou documentos correspondentes.

Exemplos: "Quanto temos a faturar neste fechamento?" e "Quais documentos foram usados?". Se pedir um novo processamento, confira a competencia e os arquivos exibidos antes de confirmar. A confirmacao repetida da mesma proposta nao cria outro fechamento. Um mes sem documentos nao possui valores conhecidos no Lastro.

A resposta sobre notas a emitir foi verificada com chamada real e referencia de R$243.284,29; um segundo cenario verificou abstencao para competencia ausente. A acao de processamento passou por interface, HTTP e motor real com uma proposta de teste identificada, preservando os sete documentos e os seis CSVs. Isso verifica a execucao da acao, mas nao comprova que o modelo sempre escolhera a ferramenta correta. Respostas livres continuam sujeitas a revisao das fontes.

## Verificar

```powershell
.venv/Scripts/python.exe -m pip install pytest httpx
$env:PYTHONPATH='src'
.venv/Scripts/python.exe -m pytest tests/api tests/dom tests/int tests/assistant tests/independent -q
cd web
npm run build
```

Os testes de transporte com respostas simuladas nao comprovam chamada real ao modelo. Os testes locais nao comprovam deploy. Reexecucao do mesmo pack permite conferir estabilidade dos seis CSVs; manifestos registram identificacao e horario da execucao.

## Limites de operacao

- Condicoes comerciais exigem autoridade do Comercial; regras do fechamento exigem Helena. Uma fonte que nomeia o aprovador nao comprova aprovacao de uma condicao nova.
- Atlas permanece pendente de taxa; nao inventar contrato a partir de aba historica.
- Pendencias sao preservadas; isso nao demonstra faturamento automatico de outubro.
- Integracoes diretas Slack/WhatsApp/email nao foram implementadas. O conhecimento usado vem das fontes fornecidas e do catalogo identificado.
- Persistencia local SQLite exige volume persistente quando hospedada; disco efemero nao garante continuidade.
- Comparacao semantica de execucoes implementada; UI validada em baselines equivalentes e em alteracao sintetica isolada de R$ 64,49, sem modificar o lote oficial. Testes isolados de mudancas controladas nao equivalem a ajustes reais recebidos.
- Investigacao OpenAI executada pela API hospedada, com fontes e estado de revisao. Uma resposta com citacoes ainda pode interpretar mal uma regra; nao ha aprovacao automatica.
- Revisao de casos com investigador e critico foi executada com modelo real e encontrou limitacoes semanticas. Permanece experimental (`needs_evidence`, `semantic_quality=not_validated`); nao constitui validacao financeira. Valores, destinatarios e acoes preparados sao fornecidos pelo motor deterministico. Evidencias exigidas para encerrar uma pendencia nao sao comprovantes ja recebidos.

Aplicacao hospedada: https://api-production-6bfe.up.railway.app, com entrada por senha. A versao publicada permite criar conjuntos por competencia, enviar documentos, abrir ou baixar os originais, selecionar as fontes e processar o fechamento. O percurso foi verificado com os sete arquivos reais, incluindo os ajustes06: os seis CSVs gerados online sao byteidenticos aos arquivos locais conferidos. O fechamento atualizado e `d0c87851-99ee-4487-9486-ca6527952f79`; execucoes anteriores foram preservadas. Mes sem fontes permanece sem apuracao. A entrega local funciona sem cadastro AWS.

A atualizacao publicada em17/10/2026,17:26BRT acrescenta o assistente. Login, abertura do chat, catalogo de contextos, fontes e arquivos preservados foram conferidos no ambiente hospedado. Os testes de respostas do modelo descritos acima foram executados pela API em ambiente local; a verificacao dessa publicacao nao realizou nova inferencia paga.
