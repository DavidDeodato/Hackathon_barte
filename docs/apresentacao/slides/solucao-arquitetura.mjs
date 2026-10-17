import fs from 'node:fs/promises';
import { palette as C } from './abertura.mjs';

export const reviewedCommit = 'b43e80e521646cc46b09e8f2c920fb035c20644d';
const repo = `https://github.com/DavidDeodato/Hackathon_barte/blob/${reviewedCommit}`;

export const continuation = [
  { index: 10, topic: 'A regra de cada operação', speech: ['Para juntar essas informações, a gente precisa saber qual regra vale para cada operação.', 'Uma taxa depende do contrato e da data. Um estorno precisa respeitar a venda original.'] },
  { index: 11, topic: 'Entrada do Lastro', speech: ['Foi esse processo que a gente organizou no Lastro.'] },
  { index: 12, topic: 'Definição do Lastro', speech: ['O Lastro é um gerenciador inteligente do fechamento financeiro da Tarvo.', 'Ele reúne os arquivos e as regras da operação, apura as comissões, confere as cobranças e organiza as pendências para revisão do financeiro.'] },
  { index: 13, topic: 'Arquivos originais', speech: ['A analista começa pelos arquivos que o financeiro já recebe.', 'O Lastro lê o relatório da Orbe e seus ajustes, o anexo do e-mail da Ponte, a planilha de taxas e os extratos dos dois bancos, junto com o plano de contas.'] },
  { index: 14, topic: 'Operação e condição aplicável', speech: ['Depois, ele relaciona os identificadores da operação ao lojista e à condição comercial válida naquela data.', 'As orientações do financeiro ficam registradas com suas fontes. O que ainda depende de confirmação continua como hipótese ou pendência.'] },
  { index: 15, topic: 'Checkout', speech: ['No checkout, ele calcula a comissão pela condição contratada e compara com a taxa que foi aplicada.', 'Estornos e reversões entram com o tratamento da operação original. A soma é feita a partir dos valores de cada linha.'] },
  { index: 16, topic: 'Remessas', speech: ['Nas remessas, ele calcula os 50% de participação da Tarvo sobre o spread realizado elegível.', 'Também verifica duplicidades e diferenças em relação ao contrato. Os spreads negativos contestados ficam fora da comissão e seguem como pendência.'] },
  { index: 17, topic: 'Bancos', speech: ['Nos extratos, ele propõe a classificação de cada movimento no plano de contas.', 'Um recebimento pode baixar uma comissão de agosto. Uma transferência pode continuar em trânsito no fim de setembro. O tratamento depende da natureza do movimento.'] },
  { index: 18, topic: 'Entregas do fechamento', speech: ['As três frentes alimentam as entregas pedidas no desafio.', 'São seis arquivos: comissões, divergências, notas a emitir, lançamentos classificados, pendências e rastro.', 'As notas ficam preparadas para revisão. A emissão fiscal continua fora desse fluxo.'] },
  { index: 19, topic: 'Origem de cada valor', speech: ['Ao abrir um valor, a analista encontra as operações que formam aquele total, a regra aplicada e a referência da fonte.', 'A soma dessas contribuições precisa conferir com o resultado apresentado.'] },
  { index: 20, topic: 'Exemplo Rota Global', speech: ['Vamos abrir a Rota Global para conferir esse caminho.', 'O líquido preparado para revisão é de R$ 1.546,28. Uma das operações contribui com R$ 66,28: taxa contratada de 3,59%, aplicada de 4,09%, com origem na linha 749 da Orbe.', 'O valor está preparado para revisão da Helena e eventual contestação à Orbe. Isso não comprova envio nem recuperação.'] },
  { index: 21, topic: 'Entrada na arquitetura agêntica', speech: ['Até aqui, vimos como o Lastro apura os valores e mostra suas origens.', 'Agora vamos entrar na arquitetura agêntica: como esses resultados viram um caso para investigação e revisão.'] },
  { index: 22, topic: 'Pacote do caso', speech: ['A partir da apuração, o sistema monta um pacote do caso.', 'Ele reúne valor, composição, natureza da ação, fontes, responsável e o que falta para encerrar a pendência.'] },
  { index: 23, topic: 'Investigador', speech: ['O investigador recebe esse pacote e usa ferramentas para localizar as regras e as referências que ajudam a interpretar o caso.', 'Ele pode buscar regras, consultar uma referência, ler uma fonte cadastrada e verificar pendências. A interpretação vem acompanhada das evidências consultadas.'] },
  { index: 24, topic: 'Crítico', speech: ['Depois, outro papel examina a interpretação: o crítico.', 'Ele recebe o mesmo pacote, a conclusão do investigador e as evidências recuperadas. Procura contradições, generalizações e decisões sem sustentação suficiente.', 'Nesta implementação, o crítico examina esse material recebido. Ele não faz uma nova busca de ferramentas.'] },
  { index: 25, topic: 'Decisão humana', speech: ['O resultado dessa investigação volta para a analista com as fontes, as observações e o que ainda precisa de confirmação.', 'Os valores continuam vinculados à apuração. Helena e o Comercial mantêm as decisões que lhes cabem.', 'O parecer é experimental e ainda precisa ser conferido. A conclusão do modelo não aprova, envia ou movimenta recursos.'] },
];

function txt(slide, name, value, x, y, width, height, size = 28, options = {}) {
  const shape = slide.shapes.add({ geometry: 'textbox', name,
    position: { left: x, top: y, width, height }, fill: 'none', line: { fill: 'none', width: 0 } });
  shape.text = value;
  shape.text.style = { typeface: 'Arial', fontSize: size, color: options.color || C.ink,
    bold: options.bold ?? false, alignment: options.align || 'left',
    verticalAlignment: options.middle ? 'middle' : 'top', autoFit: 'none', wrap: 'none', insets: 0 };
  return shape;
}

function node(slide, name, label, x, y, width, height, active = false, size = 26, ellipse = false) {
  const shape = slide.shapes.add({ geometry: ellipse ? 'ellipse' : 'rect', name,
    position: { left: x, top: y, width, height },
    fill: active ? C.accent : C.soft,
    line: { style: 'solid', fill: active ? C.accent : C.border, width: 1.5 } });
  shape.text = label;
  shape.text.style = { typeface: 'Arial', fontSize: size, bold: active,
    color: active ? C.white : C.ink, alignment: 'center', verticalAlignment: 'middle',
    autoFit: 'none', wrap: 'none', insets: 8 };
  return shape;
}

function link(slide, from, to, options = {}) {
  return slide.shapes.connect(from, to, {
    kind: options.kind || 'straight', fromSide: options.fromSide || 'right', toSide: options.toSide || 'left',
    line: { style: options.dashed ? 'dashed' : 'solid', fill: options.color || C.accent, width: options.width || 2 },
    tail: { type: 'triangle', width: 'sm', length: 'sm' },
    ...(options.both ? { head: { type: 'triangle', width: 'sm', length: 'sm' } } : {}),
  });
}

function segment(slide, name, x1, y1, x2, y2, arrow = false) {
  return slide.shapes.add({ geometry: 'connector', name, kind: 'straight',
    position: { left: Math.min(x1, x2), top: Math.min(y1, y2), width: Math.abs(x2 - x1), height: Math.abs(y2 - y1) },
    line: { style: 'dashed', fill: C.muted, width: 1.5 },
    ...(arrow ? { tail: { type: 'triangle', width: 'sm', length: 'sm' } } : {}) });
}

function base(presentation, entry, dark = false) {
  const slide = presentation.slides.add({ width: 1280, height: 720 });
  slide.background.fill = dark ? C.ink : C.canvas;
  txt(slide, `page-${entry.index}`, String(entry.index), 1158, 654, 36, 28, 18,
    { align: 'right', color: dark ? '#A9D4BF' : C.muted });
  if (entry.index !== 11) txt(slide, 'lastro-context', 'Lastro', 88, 62, 250, 68, 46,
    { bold: true, color: dark ? C.white : C.ink });
  let references = `${repo}/src/tarvo/finance/engine.py\n${repo}/contexto/RESPOSTAS_FINANCEIRO.md`;
  if (entry.index >= 21) references += `\n${repo}/src/tarvo/finance/cases.py\n${repo}/src/tarvo/agents/case_review.py\n${repo}/src/tarvo/agents/service.py`;
  if (entry.index === 20) references += `\n${repo}/saida/rota_packet.json`;
  slide.speakerNotes.text = entry.speech.map(value => `• ${value}`).join('\n') + '\n\nFontes:\n' + references;
  if (entry.index >= 21) slide.speakerNotes.text += '\n\nReferências de abstração visual: https://mktbarte.github.io/cases/case-comp.html e https://mktbarte.github.io/cases/case-sallve.html. Diagrama próprio do Lastro, com relações limitadas à implementação consultada. O destaque indica o tópico atual, sem representar execução ou aprovação.';
  return slide;
}

function title(slide, value, options = {}) {
  return txt(slide, 'main-topic', value, 88, options.y || 157, 1104, options.height || 140,
    options.size || 54, { bold: true, color: options.dark ? C.white : C.ink });
}

function processing(slide, stage) {
  const roles = ['Checkout', 'Remessas', 'Bancos'];
  const labels = ['Comissão contratada\nComparação de taxas', '50% do spread elegível\nDuplicidades e contestação', 'Conta proposta\nJustificativa e origem'];
  const xs = [168, 552, 936];
  for (let i = 0; i < stage; i++) {
    const active = i === stage - 1;
    node(slide, `processing-${i}`, roles[i], xs[i], 350, 176, 176, active, 27, true);
    txt(slide, `processing-description-${i}`, labels[i], xs[i] - 85, 554, 346, 90, 26,
      { align: 'center', color: active ? C.accent : C.muted });
  }
}

function architecture(slide, stage) {
  const labels = ['Apuração\ne rastro', 'Pacote\ndo caso', 'Investigador', 'Crítico', 'Decisão\nhumana'];
  const nodes = [];
  for (let i = 0; i <= stage; i++) {
    nodes.push(node(slide, `architecture-${i}`, labels[i], 88 + i * 232, 390, 176, 94, i === stage, 26));
    if (i > 0) link(slide, nodes[i - 1], nodes[i]);
  }
  txt(slide, 'link-financial', 'valor e rastro', 220, 338, 180, 34, 23, { align: 'center', color: C.muted });
  if (stage >= 2) {
    txt(slide, 'link-case', 'caso', 484, 338, 112, 34, 23, { align: 'center', color: C.muted });
    const sources = node(slide, 'investigator-sources', 'Fontes\ncadastradas', 546, 558, 188, 76, false, 25);
    link(slide, nodes[2], sources, { fromSide: 'bottom', toSide: 'top', both: true });
    txt(slide, 'query-label', 'consulta', 427, 512, 119, 34, 23, { color: C.muted, align: 'right' });
    txt(slide, 'evidence-label', 'evidências', 746, 512, 140, 34, 23, { color: C.muted });
  }
  if (stage >= 3) {
    txt(slide, 'interpretation-label', 'interpretação\ne evidências', 680, 323, 208, 60, 23, { color: C.muted, align: 'center' });
    // A separate, explicitly labelled channel carries the same packet to the critic.
    // The routed segments are native editable connectors, outside the main row.
    segment(slide, 'packet-critic-up', 408, 296, 408, 390);
    segment(slide, 'packet-critic-across', 408, 296, 872, 296);
    segment(slide, 'packet-critic-down', 872, 296, 872, 390, true);
    txt(slide, 'packet-critic-label', 'mesmo pacote do caso', 494, 251, 300, 34, 23, { color: C.muted, align: 'center' });
  }
  if (stage === 4) txt(slide, 'review-label', 'parecer', 946, 338, 112, 34, 23, { color: C.muted, align: 'center' });
  if (stage === 1) {
    txt(slide, 'packet-content', 'Valor e origens\nRegras e contexto\nAção e responsável', 552, 364, 600, 182, 32, { color: C.accent });
  }
  if (stage === 3) txt(slide, 'critic-limit', 'O crítico examina as evidências recebidas.', 88, 648, 1000, 36, 25, { color: C.muted });
  if (stage === 4) {
    txt(slide, 'human-owner', 'Helena ou Comercial', 970, 512, 262, 42, 25, { color: C.accent, align: 'center' });
    txt(slide, 'review-limit', 'Parecer experimental. Decisão financeira com o responsável.', 88, 648, 1040, 36, 25, { color: C.muted });
  }
}

async function author(presentation, entry, input) {
  const n = entry.index;
  const slide = base(presentation, entry, n === 21);
  if (n === 10) {
    title(slide, 'Cada operação\nprecisa da\nregra certa', { size: 60, y: 229, height: 290 });
    const operation = node(slide, 'operation', 'Operação', 760, 378, 260, 94, true, 32);
    const contract = node(slide, 'contract', 'Contrato', 678, 220, 208, 76, false, 28);
    const date = node(slide, 'validity', 'Vigência', 962, 220, 208, 76, false, 28);
    link(slide, contract, operation, { fromSide: 'bottom', toSide: 'top' });
    link(slide, date, operation, { fromSide: 'bottom', toSide: 'top' });
    txt(slide, 'original-operation', 'Um estorno remete\nà venda original.', 748, 536, 420, 92, 29, { color: C.muted });
  } else if (n === 11) {
    slide.images.add({ svg: await fs.readFile(input.logoPath, 'utf8'), alt: 'Marca Lastro', fit: 'contain',
      position: { left: 88, top: 250, width: 598.4, height: 123.2 } });
  } else if (n === 12) {
    definitionContent(slide);
  } else if (n === 13) {
    txt(slide, 'main-topic', 'Recebe os arquivos\ncomo chegam', 88, 248, 560, 250, 56, { bold: true });
    const sources = ['Orbe e ajustes', 'E-mail da Ponte', 'Taxas e contas', 'Dois bancos'];
    const receiver = node(slide, 'structured-data', 'Dados', 1058, 347, 140, 140, true, 30, true);
    sources.forEach((value, i) => {
      const source = node(slide, `input-${i}`, value, 688, 198 + i * 119, 248, 76, false, 27);
      link(slide, source, receiver, { kind: 'elbow' });
    });
  } else if (n === 14) {
    txt(slide, 'main-topic', 'Liga cada operação\nà condição aplicável', 88, 224, 590, 220, 51, { bold: true });
    txt(slide, 'unconfirmed-condition', 'Informação sem confirmação\npermanece pendente.', 88, 508, 570, 104, 29, { color: C.muted });
    const operation = node(slide, 'matched-operation', 'Operação', 844, 368, 210, 100, true, 30);
    const merchant = node(slide, 'merchant', 'Lojista', 680, 208, 196, 76, false, 28);
    const condition = node(slide, 'condition', 'Contrato\ne vigência', 984, 196, 208, 98, false, 27);
    const humanContext = node(slide, 'finance-context', 'Orientação do financeiro', 754, 558, 440, 72, false, 27);
    link(slide, merchant, operation, { fromSide: 'bottom', toSide: 'top' });
    link(slide, condition, operation, { fromSide: 'bottom', toSide: 'top' });
    link(slide, humanContext, operation, { fromSide: 'top', toSide: 'bottom' });
  } else if (n >= 15 && n <= 17) {
    const titles = ['Apura o checkout', 'Apura as remessas', 'Classifica os movimentos bancários'];
    title(slide, titles[n - 15], { size: n === 17 ? 50 : 56 });
    processing(slide, n - 14);
  } else if (n === 18) {
    title(slide, 'Reúne os resultados do fechamento', { size: 51 });
    const result = node(slide, 'closing-results', 'Resultados', 504, 396, 206, 94, true, 29);
    ['Checkout', 'Remessas', 'Bancos'].forEach((value, i) => {
      const source = node(slide, `result-source-${i}`, value, 116, 304 + i * 116, 238, 72, false, 28);
      link(slide, source, result, { kind: 'elbow' });
    });
    const outputs = txt(slide, 'six-deliverables', 'Comissões\nDivergências\nNotas a emitir\nLançamentos classificados\nPendências\nRastro', 840, 280, 378, 340, 29);
    link(slide, result, outputs);
    txt(slide, 'invoice-state', 'Notas propostas para revisão.', 88, 648, 1040, 36, 25, { color: C.muted });
  } else if (n === 19) {
    title(slide, 'Cada valor aponta para a origem');
    const labels = ['Resultado', 'Operações', 'Regra', 'Arquivo'];
    const descriptions = ['Total apresentado', 'Linhas que\ncompõem o valor', 'Condição e\nvigência aplicadas', 'Referência exata\nda fonte'];
    let previous;
    labels.forEach((value, i) => {
      const current = node(slide, `trace-${i}`, value, 88 + i * 292, 358, 228, 94, i === 0, 30);
      if (previous) link(slide, previous, current);
      txt(slide, `trace-description-${i}`, descriptions[i], 88 + i * 292, 494, 228, 100, 25, { color: C.muted, align: 'center' });
      previous = current;
    });
  } else if (n === 20) {
    title(slide, 'Rota Global', { size: 58 });
    txt(slide, 'amount-meaning', 'Diferença líquida preparada para revisão', 88, 251, 1104, 48, 30, { color: C.muted });
    txt(slide, 'prepared-amount', 'R$ 1.546,28', 88, 344, 630, 136, 90, { bold: true, color: C.accent });
    txt(slide, 'signed-components', 'R$ 1.644,72 em diferenças positivas\nR$ 98,44 de abatimento por estornos', 88, 516, 640, 96, 28, { color: C.muted });
    txt(slide, 'sample-operation', 'Operação TX88423647', 772, 334, 422, 42, 26, { bold: true });
    txt(slide, 'contracted-rate', '3,59% contratados', 772, 401, 422, 44, 30);
    txt(slide, 'applied-rate', '4,09% aplicados', 772, 456, 422, 44, 30);
    txt(slide, 'line-difference', 'R$ 66,28 de diferença', 772, 521, 422, 48, 31, { bold: true, color: C.accent });
    txt(slide, 'source-locator', 'Orbe, linha 749. Taxas vigentes da Rota Global.', 88, 648, 1040, 36, 24, { color: C.muted });
    slide.speakerNotes.text += '\n\nExemplo nativo de apuração, não captura de uma execução da interface. Pacote atualizado close-2068e24a102ebea3, estado prepared_for_review. Operação: 01_orbe_relatorio_comissoes_set2026.csv#TX88423647@L749. Contrato: 02_tabela_taxas_contratadas.xlsx#Taxas vigentes!A10:L10. Não houve novo recálculo independente nesta etapa de produção dos slides.';
  } else if (n === 21) {
    title(slide, 'Arquitetura agêntica', { dark: true, size: 62, y: 211 });
    txt(slide, 'architecture-entry', 'Como o Lastro investiga um caso', 88, 327, 1104, 72, 38, { color: '#A9D4BF' });
    const financialBase = node(slide, 'financial-base', 'Apuração e rastro', 88, 506, 350, 94, false, 32);
    const investigation = txt(slide, 'assisted-review', 'Investigação assistida', 650, 524, 540, 68, 36, { color: C.white });
    link(slide, financialBase, investigation, { color: '#A9D4BF' });
  } else if (n >= 22 && n <= 25) {
    const titles = ['O caso reúne valor e contexto', 'O investigador consulta as fontes', 'O crítico confronta a interpretação', 'A revisão volta para quem decide'];
    title(slide, titles[n - 22], { size: 51, height: 95 });
    architecture(slide, n - 21);
  }
  return slide;
}

export async function buildContinuation({ presentation, input }) {
  const indices = input.indices || [];
  if (indices.some((n, i) => n < 10 || n > 25 || !Number.isInteger(n) || (i && n !== indices[i - 1] + 1))) {
    throw new Error('Select a consecutive batch within slides 10–25.');
  }
  const authored = [], preserved = [];
  for (const index of indices) {
    if (index < presentation.slides.items.length) {
      preserved.push(index);
      continue;
    }
    if (index !== presentation.slides.items.length) throw new Error('Missing preceding slide; no blank slide inserted.');
    await author(presentation, continuation.find(item => item.index === index), input);
    authored.push(index);
  }
  if (authored.length) await presentation.render({ slide: authored });
  return { totalSlides: presentation.slides.items.length, authored, preserved,
    slides: presentation.slides.items.map((slide, index) => ({ index, id: slide.toSnapshot().aid })) };
}

function definitionContent(slide, existing) {
  const value = 'O Lastro é um gerenciador inteligente\ndo fechamento financeiro da Tarvo.';
  const heading = existing || txt(slide, 'lastro-definition', value, 88, 212, 1104, 160, 52);
  if (existing) {
    heading.position = { left: 88, top: 212, width: 1104, height: 160 };
    heading.text = value;
    heading.text.style = { typeface: 'Arial', fontSize: 52, color: C.ink,
      alignment: 'left', verticalAlignment: 'top', autoFit: 'none', wrap: 'none', insets: 0 };
  }
  heading.text.get('gerenciador inteligente').bold = true;
  heading.text.get('gerenciador inteligente').fill = C.accent;
  const detail = txt(slide, 'definition-detail', 'Ele reúne os arquivos e as regras da operação,\napura as comissões, confere as cobranças e\norganiza as pendências para revisão do financeiro.', 88, 420, 1104, 174, 37, { color: C.muted });
  return { headingId: heading.toSnapshot().aid, detailId: detail.toSnapshot().aid };
}

export async function refineDefinition({ presentation, input }) {
  const slide = presentation.slides.getItem(12);
  const ids = definitionContent(slide, presentation.resolve(input.definitionId));
  slide.speakerNotes.text = continuation.find(item => item.index === 12).speech.map(value => `• ${value}`).join('\n')
    + `\n\nFontes: ${repo}/src/tarvo/finance/engine.py e ${repo}/src/tarvo/agents/case_review.py`;
  await presentation.render({ slide: 12 });
  return ids;
}
