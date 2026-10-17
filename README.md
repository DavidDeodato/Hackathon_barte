# Lastro — fechamento Tarvo

Preparar o fechamento de setembro de 2026 com origem por numero, pendencias explicitas e investigacao das regras aplicaveis. O motor financeiro e deterministico; a camada de investigacao distingue consulta local, inferencia real e replay de teste. Propostas nao aprovam regras nem emitem notas fiscais.

## Estado verificavel

O pacote recebido gera os seis CSVs em `saida/`. Auditoria independente cobriu formato, rastro, conservacao e casos materiais; existem limites de revisao historica e a entrada integral de ajustes tardios ainda nao foi incorporada. As notas sao propostas para revisao, nao documentos fiscais emitidos. Nao apresentar este baseline como fechamento atualizado completo.

## Executar do zero

Requer Python 3.14 e Node.js 22 ou superior. A verificacao local usa Python 3.14 e Node 24. Os arquivos originais devem estar em `contexto/data_pack/`, sem limpeza manual. O pack nao esta embutido na imagem Docker nem nas credenciais.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
$env:PYTHONPATH='src'
.venv/Scripts/python.exe -m tarvo.cli --input-dir contexto/data_pack --output-dir saida --period 2026-09
```

As seis saidas: `comissoes_por_lojista.csv`, `divergencias_taxa.csv`, `notas_a_emitir.csv`, `lancamentos_classificados.csv`, `pendencias.csv`, `rastro.csv`. Separador `;`, decimal com ponto, datas ISO. `manifest.json`, `detalhes.json` e `reconciliacao.json` complementam a verificacao das entradas e dos resultados.

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

Abra `http://127.0.0.1:5173`. Use a conexao local com base vazia para o proxy `/api`. Nao execute dois servidores sobre o mesmo diretorio de estado. O modo local permite apenas acesso loopback sem token; producao exige autenticacao e origens CORS explicitas. O frontend nunca recebe a chave do provedor de IA.

## Verificar

```powershell
.venv/Scripts/python.exe -m pip install pytest httpx
$env:PYTHONPATH='src'
.venv/Scripts/python.exe -m pytest tests/api tests/dom tests/int tests/independent -q
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
- Comparacao semantica de execucoes implementada; UI validada em baselines equivalentes. Testes isolados de mudancas controladas nao equivalem a ajustes reais recebidos.
- Investigacao OpenAI executada pela API hospedada, com fontes e estado de revisao. Uma resposta com citacoes ainda pode interpretar mal uma regra; nao ha aprovacao automatica.

Backend de demonstracao: https://api-production-6bfe.up.railway.app (autenticacao obrigatoria; /api/health publico). Teste hospedado gerou seis CSVs e uma investigacao com modelo real; fechamento continua parcial e sujeito a revisao. A entrega local funciona sem cadastro AWS.
