# Apresentação Lastro

Base de trabalho para desenvolver o pitch e os slides sobre o fechamento financeiro da Tarvo. O roteiro registra as orientações do usuário; as sugestões de execução e os trechos ainda em aberto aparecem identificados.

## Documentos

- [Direção e roteiro](roteiro.md): capa e abertura dos slides 0 a 9; continuação proposta dos slides 10 a 31, com definição do Lastro, explicação por tópicos, arquitetura progressiva e relação setembro/outubro.
- [Referências de apresentação](referencias.md): padrões observados na Barte, aplicações possíveis e limites da referência.
- [Slides do pitch](slides/README.md): 50 avanços da capa ao encerramento, incluindo resultados, demo, limites e plano de um mês, com prévias e fontes de construção da apresentação editável.
- [Orientações do desafio](../../contexto/instrucoes_extraidas.txt): requisitos usados como fonte, sujeitos à conferência com a organização.
- [Respostas do financeiro](../../contexto/RESPOSTAS_FINANCEIRO.md): contexto recebido sobre regras e decisões do fechamento.
- [Estado do produto](../../README.md): execução, validação e limites da implementação.

## Como avançar

A capa, a abertura e a continuação até a arquitetura já estão desenvolvidas nos slides 0 a 25. Preservar a progressão das três frentes, a presença de Helena e a revelação de um tópico por avanço. Desenvolver em seguida o uso completo na interface, as pendências e a continuidade dos slides 26 a 31. O ensaio com a aplicação e a validação do tempo ainda precisam ser realizados.

Depois da entrada, definir o Lastro como gerenciador inteligente do fechamento financeiro e descrever o trabalho que ele organiza. Explicar recebimento, cruzamento, apuração e rastro antes de entrar na arquitetura agêntica. Nesse bloco, anunciar a mudança de assunto e revelar pacote do caso, investigador, crítico e revisão humana em avanços sucessivos.

Setembro é a competência que o desafio exige fechar, incluindo os ajustes tardios obrigatórios. Outubro testa o reaproveitamento do processo e a continuidade de obrigações e decisões entre competências. Conferir os resultados atualizados de setembro precede o plano de evolução do produto.

A logo confirmada da Tarvo e a identificação do time continuam pendentes. Helena aparece pelo nome na primeira versão. Usar os estados e valores efetivos do produto na demonstração. Qualificar propostas, investigações experimentais e pendências para que não sejam apresentadas como decisões aprovadas ou dinheiro recuperado.

## Versionamento durante a produção

Conforme solicitado pelo usuário, registrar cada etapa coerente em um commit descritivo: roteiro, composição de um bloco, implementação visual ou correção verificada. Concluir e conferir o bloco antes de fazer o commit; evitar commits intermediários que deixem a apresentação sem funcionar.

Antes de cada commit:

1. Conferir a branch, a base e as alterações existentes, preservando o trabalho de outras pessoas.
2. Revisar o diff e incluir apenas os arquivos correspondentes à etapa.
3. Validar os links e o texto nas mudanças de documentação. Em mudanças executáveis, realizar a compilação e os testes pertinentes; nos slides, conferir também a renderização e a navegação.
4. Registrar o commit e verificar o estado da árvore de trabalho. Documentar qualquer limitação de validação.

Preservar os commits existentes. Publicar alterações em branch própria e integrar por revisão, sem reescrever o histórico compartilhado. Se a branch de origem avançar, examinar as mudanças antes de integrar. Esta orientação vale para a execução acompanhada da apresentação; não configura uma automação em segundo plano.

## Base desta documentação

Incorporada sobre a `main` em `59ee5c8`, de 17/10/2026. O commit `93ffa23` integrou a mesa de casos à interface principal; `59ee5c8` acrescenta registros públicos de conversas. A conferência técnica da interface foi estática. Uma demonstração deve ser ensaiada na versão efetivamente utilizada.

Na construção da continuação visual, foram consultadas remotamente as atualizações até [`b43e80e`](https://github.com/DavidDeodato/Hackathon_barte/commit/b43e80e521646cc46b09e8f2c920fb035c20644d), que incorpora os ajustes tardios e publica novas saídas. O pacote Rota confirma o líquido de R$ 1.546,28 preparado para revisão. O aviso anterior de revisão pendente, baseado em `7d22eb1`, foi atualizado no roteiro. Os commits remotos foram inspecionados como fontes; não foram integrados automaticamente à branch local da apresentação.

## Versão com evidências de avaliação

[PowerPoint completo](Lastro_pitch.pptx): 50 avanços, mantendo a base visual e as notas. [Percurso da demo](demo.md): controles, duração de ensaio, modos de execução e alternativa para falhas. A continuação usa os CSVs publicados, os hashes e a pergunta de David confirmada pelo financeiro. Capturas reais de consulta documental não são apresentadas como processamento novo ou como modelo executado. Benefício de tempo e continuidade integral de outubro seguem como verificações futuras.
