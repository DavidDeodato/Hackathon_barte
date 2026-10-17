# Pergunta enviada por David: data-base da isenção de antecipação

Fonte: pergunta e resposta transcritas por Lorena nesta revisão do pitch. A organização identifica a resposta como “Resposta para David”, por `manuel.freitas`, às 13h34, no papel de Helena. O envio é confirmado pelo relato da participante e pela resposta fornecida; o link da mensagem e o nome do time não foram fornecidos. Não houve nova consulta autenticada ao Slack.

## Pergunta

> [Financeiro] A isenção da Casa do Estudante inclui antecipação de setembro a dezembro. Para essa tarifa, a isenção vale pela data da antecipação ou pela data das vendas que geraram os recebíveis? Ex: a AN88445172 ocorreu em 09/09, mas não traz referência nem data das vendas originais. Se ela antecipou recebíveis de agosto, a tarifa também fica zerada? Ou precisamos identificar essas vendas antes de calcular a comissão e a devolução?

## Resposta recebida

> [Financeiro] Resposta para David Vale pela data da antecipação. A antecipação é um serviço que a gente presta no dia em que ela acontece: se foi em setembro, está dentro da isenção. Não precisa ir atrás das vendas de origem. — Helena

## Efeito na interpretação e evidência

A isenção da tarifa de antecipação usa a data da própria antecipação. Essa resposta dispensa buscar vendas originadoras para decidir a isenção desse serviço. Estornos de vendas continuam sujeitos à data e à regra da venda original; a resposta não altera esse tratamento.

Em `saida/detalhes.json`, a `AN88445172` tem data `2026-09-09`, origem na linha 509 de `01_orbe_relatorio_comissoes_set2026.csv`, taxa esperada zero e comissão `0.00`. O resultado publicado já aplica esse tratamento. A nova resposta confirma a regra e resolve a premissa documental; não comprova que houve alteração posterior do motor.

O valor cobrado informado é `103.69`. A diferença calculada pelo critério de bruto × diferença de taxa, arredondada por operação, é `103.70`. Esses campos não têm significado idêntico. Não apresentar um deles como transcrição do outro.

O registro anterior de pergunta apenas preparada em `PROMPTS/SESSAO_001.md` permanece como histórico daquela etapa. Esta evidência posterior complementa o histórico, sem reescrever as mensagens originais.
