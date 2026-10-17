# Conversas públicas — registro textual real

Os arquivos `.jsonl` contêm mensagens reais de usuário e assistente extraídas das sessões do projeto. Cada linha traz `source_record` (posição no snapshot de origem), `timestamp`, `role`, `phase` e `content`. A ordem de cada conversa foi preservada. Não há textos de preenchimento nem conversas inventadas.

O [manifesto](manifest.json) registra os hashes dos arquivos publicados e dos snapshots de origem, a data de captura e as contagens de registros incluídos ou omitidos. Os snapshots brutos não são publicados.

## Omissões declaradas

- Chamadas e resultados de ferramentas: podem conter credenciais, memória operacional e arquivos privados; seus corpos não entram neste recorte.
- Mensagens internas entre agentes, instruções automáticas de runtime e conteúdo de raciocínio privado.
- Imagens, áudio e metadados internos. Anexos omitidos não foram substituídos por descrições inventadas.
- Credenciais conhecidas e padrões de segredo, e-mails, referências privadas de memória e identificadores pessoais de caminhos locais são removidos ou substituídos por marcadores explícitos.

As contagens distinguem mensagens públicas, partes omitidas e partes redigidas. Esta é uma seleção pública do histórico textual, não uma declaração de que todos os registros técnicos foram publicados. Sessões em andamento precisam de novo snapshot para incluir mensagens futuras.

## Leitura

Cada arquivo é JSON Lines em UTF-8. Pode ser aberto como texto, ou lido com Python:

```python
import json
from pathlib import Path

for arquivo in sorted(Path('PROMPTS/conversas_publicas').glob('*.jsonl')):
    for linha in arquivo.read_text(encoding='utf-8').splitlines():
        mensagem = json.loads(linha)
        print(mensagem['timestamp'], mensagem['role'])
        print('\n'.join(mensagem['content']))
```
