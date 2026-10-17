# Histórico de uso de IA

O registro público das conversas está em [conversas_publicas/](conversas_publicas/README.md). Ele preserva mensagens textuais reais de usuário e assistente, na ordem disponível de cada sessão. O manifesto informa o horário do snapshot, as contagens, os hashes e as omissões. Não é uma exportação integral bruta nem um histórico reconstruído.

- [MOMENTOS.md](MOMENTOS.md): decisões e correções materiais pelo participante.
- [SESSAO_001.md](SESSAO_001.md): recortes iniciais para navegação.
- [conversas_publicas/manifest.json](conversas_publicas/manifest.json): inventário verificável das sessões publicadas.
- [conversas_publicas/omissions.jsonl](conversas_publicas/omissions.jsonl): posição e motivo de cada omissão, sem o conteúdo privado.

O exportador reproduzível está em `tools/export_prompt_history.py`, com testes de privacidade em `tests/test_public_history.py`. As sessões originais são locais e não acompanham o repositório. O exportador seleciona o projeto pelo diretório registrado nos metadados; não reconstrói mensagens ausentes.

Por privacidade, não são publicados corpos ou resultados de ferramentas, mensagens internas entre agentes, instruções de sistema/runtime, raciocínio privado, imagens, credenciais ou informações pessoais de contato. Essas omissões são declaradas, sem substituí-las por diálogos fabricados. Os históricos brutos permanecem locais.

Sessões ainda em andamento podem ter mensagens posteriores ao snapshot. Perguntas apenas preparadas não são perguntas enviadas ao financeiro; execução técnica, resultado de modelo e aprovação financeira permanecem distintos.
