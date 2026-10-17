# Investigação I-INV v1.1

`from tarvo.agents.service import investigate` expõe o contrato `investigate(question, run_context) -> dict`.
Python >= 3.10, somente biblioteca padrão. `PYTHONPATH=src` ou inserir `src` no ambiente de execução do backend.

Contexto de servidor: `project_root`, `output_dir`, `run_id`, `period`, `as_of` opcional e `mode`.
Assinatura consumida pela API sem acesso a credenciais. Caminhos e adaptadores são fornecidos pelo servidor; nunca repassar o JSON do cliente inteiro como contexto.

- `deterministic` é o padrão: busca lexical de regras citadas, referências exatas nas saídas e rastro, leitura de pendências quando solicitadas. Não chama LLM.
- `llm` exige callable interno `model_adapter`. Ausência retorna `unavailable`, sem resposta simulada ou fallback silencioso. `openai_transport.py` implementa o transporte; somente o coordenador valida a chamada real autorizada.
- `replay` exige callable interno `replay_adapter`; identifica fixture e não contabiliza inferência real.

Adaptador recebe `{messages, tools, max_output_tokens}` e devolve um objeto com `tool_calls: [{id,name,arguments}]` ou `{answer,citations,proposed_changes}`. O formato é neutro e requer tradução pelo transporte do provedor. As ferramentas de fato executadas são `search_rules`, `lookup_reference`, `review_pending` e `read_source`. Leitura de fonte somente no catálogo; sem SQL nem escrita genérica. Limite de quatro chamadas ao adaptador, doze ferramentas e dez propostas. Timeout/cancelamento do transporte é responsabilidade do backend: o limite de turnos não interrompe um callable bloqueado.

Propostas podem ser fornecidas pelo adaptador ou por `change_request` interno estruturado. Texto livre no modo determinístico não é extraído como nova regra. `source_refs` e `authority_evidence_refs` precisam estar nas evidências recuperadas; referências de autoridade têm campo separado e não constituem aprovação. Datas ISO, escopo e exceções são preservados. `valid_from/to` é o contrato v1.1; aliases legados `effective_from/to` são aceitos se coerentes. `base_run_id` vem exclusivamente do servidor. Impacto sempre `not_calculated` / `null`, aplicação sempre falsa, aprovador/data sempre nulos. Nada grava regra ou altera os CSVs. Estrutura validada não prova semântica financeira correta.

Correção após QA: toda proposta nova permanece `status=needs_evidence` e inclui `specific_authority_decision_not_verified` em `validation_gaps`. Uma política dizendo que Comercial/Helena aprova não prova aprovação da condição específica; mesmo uma referência recuperada válida não promove esse estado. Este lote não possui verificador semântico de decisão/escopo/vigência.

## Transporte OpenAI e integração no processo filho

No adaptador da API que já roda dentro do subprocesso:

```python
from tarvo.agents.openai_transport import create_openai_adapter
from tarvo.agents.service import investigate

context = dict(payload['run_context'])
if context.get('mode') == 'llm':
    context['model_adapter'] = create_openai_adapter()
return investigate(payload['question'], context)
```

Instância nova por investigação. Não serializar o callable para JSON nem aceitar configurações/caminhos/adaptadores do cliente HTTP. `create_openai_adapter` lê exclusivamente `OPENAI_API_KEY` e `OPENAI_MODEL` herdados no ambiente, sem ler `.env`, e não faz chamada ao construir. Ausência de qualquer um retorna `None`/`unavailable`. Modelo é obrigatório, sem substituição ou escolha implícita.

O transporte usa HTTPS fixo para `api.openai.com/v1/responses`, biblioteca padrão, funções nativas com schema estrito, `store=false` e histórico de itens nativos em memória. Itens internos de reasoning são reenviados ao provedor conforme o protocolo, sem exposição em respostas/eventos/artefatos. Primeira chamada exige ferramenta; respostas finais são objetos JSON. Nenhuma ferramenta escreve ou aciona pagamento. Redirects são bloqueados.

Cada tentativa HTTP tem timeout de socket de 30s, sem retry. Limite de quatro tentativas e 1.800 tokens de saída por tentativa (inclui o orçamento do modelo, não mede qualidade nem custo). Requests limitados a 512 KB, respostas a 2 MB. Timeout de socket não é deadline global: o subprocesso da API mantém kill/timeout de toda a investigação, inclusive callable bloqueado. Erros 401/429/5xx/rede/resposta inválida viram códigos fixos; corpos de erro e chave não são retornados.

`result.model_metrics` preserva por tentativa provider, modelo retornado/configurado, índice, latência local em ms, HTTP status, status e tokens input/output/total reportados pela API; desconhecidos são `null`, inclusive `cost_brl` (preço não calculado). Métricas sobrevivem a falha de transporte. Não confundir métricas dos HTTP mocks com inferência real. Este braço não fez chamada paga.

Fontes conferidas em 17/10/2026: [Function calling](https://developers.openai.com/api/docs/guides/function-calling), [migração e estado de Responses](https://developers.openai.com/api/docs/guides/migrate-to-responses). Disponibilidade e qualidade do modelo escolhido dependem do teste real pelo coordenador.

O catálogo empacotado vigente deriva de 58 trechos identificados em `contexto/RESPOSTAS_FINANCEIRO.md`, fixados por SHA-256. Inclui o contexto integral da linha Atlas, além dos resumos CAN-04/CAN-19. Datas comerciais e exceções permanecem no texto; o catálogo não inventa vigência uniforme para as regras. Se a fonte mudar ou faltar, investigar retorna `blocked`. Um `config/knowledge_rules.json` existente tem precedência por compatibilidade; passa pela mesma verificação de fontes. Este fallback corrige a dependência ausente do código legado.

Atualizações após testes reais: argumentos inválidos de busca são devolvidos como observações estruturadas ao investigador, mantendo orçamento4/12 e sem omitir filtro/inventar data silenciosamente; ferramentas fora da allowlist continuam bloqueadas. O prompt distingue estado presente de condição futura: Atlas ainda não possui contrato confirmado, e só após confirmação Comercial a condição terá efeito desde10/09, com origens de setembro preservadas para faturar junto com outubro. A mudança de prompt/contexto tem regressões locais; qualidade semântica geral não está validada por elas.

Pendências mantêm conteúdo original, valor desconhecido vazio, chave estável, período de origem fornecido pelo run e referências. A fila não resolve obrigações, não fatura outubro nem oferece ledger persistido. A API é dona da persistência de investigações/eventos; comparação de runs e continuidade resolvida são lote 2.

Validação: `python -X utf8 -m unittest discover -s tests/int -p 'test_*.py' -v`.
Smoke do case: `python -X utf8 docs/agent/branches/INT/artifacts/run_smoke.py`.
Os testes de replay não medem qualidade de LLM; smoke de fontes não valida números dos seis CSVs.
