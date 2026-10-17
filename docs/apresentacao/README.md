# Apresentação Lastro

Base de trabalho para desenvolver o pitch e os slides sobre o fechamento financeiro da Tarvo. O roteiro registra as orientações do usuário; as sugestões de execução e os trechos ainda em aberto aparecem identificados.

## Documentos

- [Direção e roteiro](roteiro.md): tom, fala, capa, sequência dos slides 0 a 9 e continuidade proposta para explicar a solução.
- [Referências de apresentação](referencias.md): padrões observados na Barte, aplicações possíveis e limites da referência.
- [Orientações do desafio](../../contexto/instrucoes_extraidas.txt): requisitos usados como fonte, sujeitos à conferência com a organização.
- [Respostas do financeiro](../../contexto/RESPOSTAS_FINANCEIRO.md): contexto recebido sobre regras e decisões do fechamento.
- [Estado do produto](../../README.md): execução, validação e limites da implementação.

## Como avançar

Desenvolver primeiro a capa e a abertura já descritas no roteiro. Preservar a progressão das três frentes, a presença de Helena e a revelação de uma pergunta por avanço. A continuação técnica é uma proposta de fala; sua distribuição em slides ainda precisa ser definida.

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
