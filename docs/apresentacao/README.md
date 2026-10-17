# Apresentação Lastro

Base de trabalho para desenvolver o pitch e os slides sobre o fechamento financeiro da Tarvo. O roteiro registra as orientações do usuário; as sugestões de execução e os trechos ainda em aberto aparecem identificados.

## Documentos

- [Direção e roteiro](roteiro.md): capa e abertura dos slides 0 a 9; continuação proposta dos slides 10 a 31, com definição do Lastro, explicação por tópicos, arquitetura progressiva e relação setembro/outubro.
- [Referências de apresentação](referencias.md): padrões observados na Barte, aplicações possíveis e limites da referência.
- [Orientações do desafio](../../contexto/instrucoes_extraidas.txt): requisitos usados como fonte, sujeitos à conferência com a organização.
- [Respostas do financeiro](../../contexto/RESPOSTAS_FINANCEIRO.md): contexto recebido sobre regras e decisões do fechamento.
- [Estado do produto](../../README.md): execução, validação e limites da implementação.

## Como avançar

Desenvolver primeiro a capa e a abertura já descritas no roteiro. Preservar a progressão das três frentes, a presença de Helena e a revelação de uma pergunta por avanço. A continuação já propõe um tópico principal por slide, com bullets de fala e instruções de composição; a produção visual e o ensaio ainda precisam ser realizados.

Depois da entrada, definir o Lastro em uma frase. Explicar recebimento, cruzamento, apuração e rastro antes de entrar na arquitetura agêntica. Nesse bloco, anunciar a mudança de assunto e revelar pacote do caso, investigador, crítico e revisão humana em avanços sucessivos.

Setembro é a competência que o desafio exige fechar, incluindo os ajustes tardios obrigatórios. Outubro testa o reaproveitamento do processo e a continuidade de obrigações e decisões entre competências. Conferir os resultados atualizados de setembro precede o plano de evolução do produto.

A logo confirmada da Tarvo, a identificação do time e a representação de Helena continuam pendentes. Usar os estados e valores efetivos do produto na demonstração. Qualificar propostas, investigações experimentais e pendências para que não sejam apresentadas como decisões aprovadas ou dinheiro recuperado.

## Versionamento durante a produção

Conforme solicitado pelo usuário, registrar cada etapa coerente em um commit descritivo: roteiro, composição de um bloco, implementação visual ou correção verificada. Concluir e conferir o bloco antes de fazer o commit; evitar commits intermediários que deixem a apresentação sem funcionar.

Antes de cada commit:

1. Conferir a branch, a base e as alterações existentes, preservando o trabalho de outras pessoas.
2. Revisar o diff e incluir apenas os arquivos correspondentes à etapa.
3. Validar os links e o texto nas mudanças de documentação. Em mudanças executáveis, realizar a compilação e os testes pertinentes; nos slides, conferir também a renderização e a navegação.
4. Registrar o commit e verificar o estado da árvore de trabalho. Documentar qualquer limitação de validação.

Preservar os commits existentes. Publicar alterações em branch própria e integrar por revisão, sem reescrever o histórico compartilhado. Se a branch de origem avançar, examinar as mudanças antes de integrar. Esta orientação vale para a execução acompanhada da apresentação; não configura uma automação em segundo plano.

## Base desta documentação

Incorporada sobre a `main` em `59ee5c8`, de 17/10/2026. A última mudança de aplicação considerada no roteiro é `93ffa23`, que integrou a mesa de casos à interface principal; `59ee5c8` acrescenta registros públicos de conversas. A conferência técnica da interface foi estática. Uma demonstração deve ser ensaiada na versão efetivamente utilizada.

Na revisão do roteiro, também foram consultadas remotamente as atualizações documentais até [`7d22eb1`](https://github.com/DavidDeodato/Hackathon_barte/commit/7d22eb10d5cdf8d85275eb6bf2c07e4eb93a3db8): ajustes tardios recebidos, com promoção das saídas recalculadas ainda pendente de conferência naquele registro. Esses commits remotos não foram integrados automaticamente à branch local. Ver a fonte e os cuidados de atualização no slide 29.
