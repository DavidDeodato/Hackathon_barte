# Conversas públicas — registro textual real

Os arquivos de sessão `.jsonl` contêm mensagens reais de usuário e assistente extraídas das sessões do projeto, intercaladas com marcadores de omissão. Cada linha traz `source_record` (posição física no snapshot original), `timestamp`, `record_kind` e `content`. Mensagens têm `role` e `phase`; registros inteiramente omitidos têm `reason`, sem atribuir fala fictícia a usuário ou assistente. A ordem de cada conversa foi preservada.

O [manifesto](manifest.json) registra os hashes dos arquivos publicados e dos snapshots de origem, a data de captura e as contagens de registros incluídos ou omitidos. Os snapshots brutos não são publicados.

## Omissões declaradas

- Chamadas e resultados de ferramentas: podem conter credenciais, memória operacional e arquivos privados; seus corpos não entram neste recorte.
- Mensagens internas entre agentes, instruções automáticas de runtime e conteúdo de raciocínio privado.
- Imagens, áudio e metadados internos. Anexos omitidos não foram substituídos por descrições inventadas.
- Credenciais conhecidas e padrões de segredo, e-mails, referências privadas de memória e identificadores pessoais de caminhos locais são removidos ou substituídos por marcadores explícitos.

O [índice de omissões](omissions.jsonl) identifica sessão, posição e motivo de cada registro ou parte omitida. Os mesmos pontos recebem marcadores explícitos no arquivo da sessão. `visible_messages` conta registros com algum texto visível; `fully_omitted_messages` conta mensagens cujas partes foram todas ocultadas. `omission` conta registros internos inteiramente omitidos. Essas contagens não medem produtividade nem qualidade.

Esta é uma seleção pública do histórico textual, não uma declaração de que todos os registros técnicos foram publicados. Metadados que não são mensagens ficam fora do recorte e são contados. Linhas parciais são contadas separadamente. Os hashes de origem identificam os bytes capturados em cada sessão; sessões em andamento precisam de novo snapshot para incluir mensagens futuras.

## Leitura

Cada arquivo é JSON Lines em UTF-8. Pode ser aberto como texto, ou lido com Python:

```python
import json
from pathlib import Path

base = Path('PROMPTS/conversas_publicas')
manifesto = json.loads((base / 'manifest.json').read_text(encoding='utf-8'))
for sessao in manifesto['sessions']:
    arquivo = base / sessao['file']
    for linha in arquivo.read_text(encoding='utf-8').splitlines():
        mensagem = json.loads(linha)
        print(mensagem['timestamp'], mensagem.get('role', 'omissão'))
        print('\n'.join(mensagem['content']))
```

Para gerar um novo recorte a partir das sessões locais, use:

```powershell
python tools/export_prompt_history.py --session-dir CAMINHO_DAS_SESSOES --destination PROMPTS/conversas_publicas
```

O comando não modifica as sessões originais nem exige APIs. A revisão de privacidade do conteúdo gerado continua necessária antes de publicá-lo.
