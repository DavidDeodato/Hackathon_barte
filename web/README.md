# Lastro · interface Tarvo

Frontend React/Vite/TypeScript da mesa de fechamento. Consome a API do projeto; não recalcula valores financeiros, não aprova regras e não substitui Helena.

## Executar localmente

Requisitos: Node.js 22.12+ ou 24+, npm e API do projeto em `127.0.0.1:8000`.

```powershell
cd web
npm ci
npm run dev -- --port 5173
```

Abra `http://127.0.0.1:5173/`. A API deve ser iniciada conforme `docs/agent/branches/API/artifacts/API_USAGE.md`, a partir da raiz do projeto.

A interface começa em **Modo demonstração** quando `VITE_API_BASE_URL` não está definida. Clique em **Conectar API**, deixe o endereço vazio para usar o proxy local e clique em **Conectar**. Nenhum número financeiro é inventado na demonstração.

Quando o backend exigir bearer, informe o token no campo de sessão. Ele permanece somente na memória da aba. Não está no código, em variável VITE, em URL, cookie ou armazenamento local. Recarregar a página descarta o token. A interface não lê o arquivo `.env` da raiz nem `.secrets`. O botão **Usar API publicada** sugere a URL HTTPS informada pelo coordenador; ele preenche o endereço sem enviar requisição ou token automaticamente.

Para build com backend em outro host, defina **somente a URL pública** em `VITE_API_BASE_URL`. O backend deve permitir a origem via CORS. Nunca coloque uma chave ou token em variável VITE. Build local não comprova deploy ou persistência cloud.

## Conferir um fechamento

1. Selecione uma execução existente ou use **Processar fechamento** para solicitar uma nova. HTTP202 é processamento, não conclusão.
2. Confira competência, estado e restrições na tela. O seletor de mês prepara a próxima execução; o rodapé mantém a competência do resultado selecionado.
3. Abra **Saídas** ou um valor no resumo. A prévia é limitada a 100 registros; **Baixar CSV** recupera o arquivo integral autenticado.
4. Em **Ver registro**, use **Conferir rastro desta saída**. O navegador baixa e interpreta o `rastro.csv` integral daquela execução e filtra o `id_saida`, inclusive além das primeiras 100 linhas.
5. Em **Pendências**, filtre motivo/referência e confira `quem_decide`. Pendência registrada não é resolvida automaticamente.
6. **Investigação** oferece **Consulta às fontes** (padrão determinístico) e **Investigação com IA**. IA envia `mode=llm` ao backend somente com bearer de sessão; autenticação/indisponibilidade permanecem explícitas, sem fallback silencioso. A resposta mostra fonte, trecho, autoridade citada, `model_called` e métricas por tentativa (tokens, HTTP, latência, custo informado). Campos ausentes aparecem como n/a; tokens não são convertidos em custo. Propostas mantêm impacto não calculado e não são aplicadas.
7. **Central de agentes** usa eventos reais da execução; não gera tarefas ou animações de trabalho fictício.
8. **O que mudou entre execuções?** compara dois resultados gravados por endpoint assíncrono. Se não houver dois resultados elegíveis, fica não calculado. Contagens e valores ficam separados por arquivo/natureza. A comparação não aprova o fechamento.

## Verificação

```powershell
npm run build
npm run qa
```

`qa` usa Playwright com Edge instalado, Vite em5173 e API em8000. `node scripts/qa-investigation-mode.mjs` testa o seletor/métricas/erros com API inteiramente simulada e screenshots rotulados, sem chamada de modelo ou credencial real. O teste não usa LLM. Registra screenshots e relatório em `docs/agent/branches/EXP/artifacts/`; solicita investigação determinística e comparação de runs reais já disponíveis. Não é gabarito independente dos cálculos do motor.

## Limites desta entrega

- Baseline recebido está marcado sem ajustes tardios e pendente de Helena. O frontend preserva esse aviso.
- Busca de texto na tabela opera sobre a prévia; não é busca da base integral.
- O rastro integral é carregado em memória no navegador; adequado ao pack atual, sem promessa de escala arbitrária.
- Comparação no navegador foi exercitada com duas baselines equivalentes: zero delta é esperado. Isso não demonstra mudança financeira não zero.
- Modo determinístico, disponibilidade de modelo, revisão técnica e aprovação financeira são estados distintos. O frontend só declara modelo acionado conforme campo retornado; isso registra tentativa, não garante conclusão da resposta.
- Sem emissão fiscal, pagamento, envio de contestação, submissão ou deploy realizado por este braço.
