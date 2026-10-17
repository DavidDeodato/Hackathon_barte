import fs from 'node:fs/promises';

// Callback for Artifact Session. It receives the connected presentation;
// it never creates another deck or changes the application/financial outputs.
export const palette = {
  canvas: '#F6F7F4', ink: '#132B2A', accent: '#1E6654',
  muted: '#586964', border: '#D7DFDA', soft: '#E7F1EC', white: '#FFFFFF',
};

export const opening = [
  ['Capa', 'Lastro. Fechamento financeiro da Tarvo.'],
  ['Tarvo', 'Essa é a Tarvo.'],
  ['Três frentes', 'Hoje, o financeiro dela se apoia em três frentes que não se conectam.'],
  ['A planilha', 'De um lado, uma planilha com as taxas e condições de cada lojista.'],
  ['Relatórios e extratos', 'Do outro, relatórios dos parceiros e extratos bancários mostrando o que foi cobrado e movimentado.'],
  ['Helena', 'E, entre essas duas pontas, a Helena, que guarda o contexto dos acordos e das exceções que os arquivos não explicam.'],
  ['Quanto pode faturar', 'No fim do mês, o time precisa juntar essas três frentes para descobrir quanto pode faturar...'],
  ['O que precisa corrigir', '...o que precisa corrigir...'],
  ['Valores pendentes', '...e quais valores continuam pendentes.'],
  ['Consequências', 'Esse trabalho leva oito dias úteis, abre espaço para cobranças incorretas e deixa o fechamento dependente de quem conhece as regras.'],
];

function text(slide, name, value, x, y, w, h, size, options = {}) {
  const shape = slide.shapes.add({
    geometry: 'textbox', name,
    position: { left: x, top: y, width: w, height: h },
    fill: 'none', line: { fill: 'none', width: 0 },
  });
  shape.text = value;
  shape.text.style = {
    typeface: 'Arial', fontSize: size,
    color: options.color || palette.ink,
    bold: options.bold ?? false,
    alignment: options.align || 'left',
    verticalAlignment: options.middle ? 'middle' : 'top',
    autoFit: 'none', wrap: 'none', insets: 0,
    ...options.style,
  };
  return shape;
}

function circle(slide, name, x, y, r, number, active = false, outline = false) {
  const shape = slide.shapes.add({
    geometry: 'ellipse', name,
    position: { left: x - r, top: y - r, width: 2 * r, height: 2 * r },
    fill: outline ? 'none' : active ? palette.accent : palette.soft,
    line: { style: 'solid', fill: outline ? palette.border : active ? palette.accent : palette.border, width: 2 },
  });
  if (number) {
    shape.text = String(number);
    shape.text.style = {
      typeface: 'Arial', fontSize: r * .82, bold: true,
      color: active ? palette.white : palette.accent,
      alignment: 'center', verticalAlignment: 'middle', insets: 0,
      autoFit: 'none', wrap: 'none',
    };
  }
  return shape;
}

function connection(slide, from, to, options = {}) {
  return slide.shapes.connect(from, to, {
    kind: 'straight',
    line: { style: options.dashed ? 'dashed' : 'solid', fill: options.color || palette.border, width: options.width || 2 },
    ...(options.fromSide ? { fromSide: options.fromSide } : {}),
    ...(options.toSide ? { toSide: options.toSide } : {}),
    ...(options.arrow ? { tail: { type: 'triangle', width: 'sm', length: 'sm' } } : {}),
  });
}

function base(presentation, index) {
  const slide = index < presentation.slides.items.length
    ? presentation.slides.getItem(index)
    : presentation.slides.add({ width: 1280, height: 720 });
  slide.background.fill = palette.canvas;
  slide.speakerNotes.text = opening[index][1]
    + '\n\nFonte: contexto/instrucoes_extraidas.txt e contexto/RESPOSTAS_FINANCEIRO.md, relato do processo atual.'
    + (index > 0 && index < 9 ? '\nIdentificação Tarvo provisória, em texto. Substituir pela logo confirmada sem alterar o restante da sequência.' : '');
  return slide;
}

function page(slide, index, dark = false) {
  text(slide, `page-${index}`, String(index).padStart(2, '0'), 1158, 654, 36, 28, 18,
    { color: dark ? '#A9D4BF' : palette.muted, align: 'right' });
}

function tarvo(slide, intro = false) {
  text(slide, 'tarvo-identification', 'Tarvo', 88, intro ? 236 : 62,
    intro ? 520 : 240, intro ? 132 : 68, intro ? 104 : 46, { bold: true });
}

function triangle(slide, stage, compact = false) {
  const pos = compact
    ? { x1: 178, x2: 482, y: 324, x3: 330, y3: 590, cx: 330, cy: 440, radius: 28 }
    : { x1: 790, x2: 1100, y: 292, x3: 945, y3: 600, cx: 945, cy: 424, radius: 34 };
  const nodes = [
    circle(slide, 'front-1', pos.x1, pos.y, pos.radius, stage >= 1 ? 1 : null, stage === 1, stage < 1),
    circle(slide, 'front-2', pos.x2, pos.y, pos.radius, stage >= 2 ? 2 : null, stage === 2, stage < 2),
    circle(slide, 'front-3', pos.x3, pos.y3, pos.radius, stage >= 3 ? 3 : null, stage === 3, stage < 3),
  ];
  if (stage >= 1) text(slide, 'front-1-label', 'Planilha de taxas', pos.x1 - 126, pos.y - 86, 252, 38, compact ? 23 : 25, { align: 'center', color: stage === 1 ? palette.accent : palette.muted });
  if (stage >= 2) text(slide, 'front-2-label', 'Relatórios e extratos', pos.x2 - 144, pos.y - 86, 288, 38, compact ? 23 : 25, { align: 'center', color: stage === 2 ? palette.accent : palette.muted });
  let helena;
  if (stage >= 3) {
    connection(slide, nodes[0], nodes[1]);
    connection(slide, nodes[0], nodes[2]);
    connection(slide, nodes[1], nodes[2]);
    helena = text(slide, 'helena-center', 'Helena', pos.cx - 106, pos.cy - 34, 212, 68, compact ? 40 : 48,
      { color: palette.accent, bold: true, align: 'center', middle: true });
    connection(slide, nodes[2], helena, { color: palette.accent, dashed: true, fromSide: 'top', toSide: 'bottom' });
    helena.bringToFront();
  }
  return { nodes, helena };
}

async function cover(presentation, input) {
  if (presentation.slides.items.length && presentation.slides.getItem(0).shapes.items.length) return;
  const slide = base(presentation, 0);
  slide.background.fill = palette.ink;
  const svg = await fs.readFile(input.logoPath, 'utf8');
  slide.images.add({
    svg, alt: 'Marca Lastro', fit: 'contain',
    position: { left: 88, top: 250, width: 598.4, height: 123.2 },
  });
  text(slide, 'cover-subtitle', 'Fechamento financeiro da Tarvo', 88, 417, 1070, 68, 38,
    { color: palette.white });
  text(slide, 'cover-period', 'Setembro de 2026', 88, 592, 700, 40, 24,
    { color: '#A9D4BF' });
  slide.speakerNotes.text = opening[0][1];
}

function develop(presentation, indices) {
  for (const index of indices) {
    if (index < presentation.slides.items.length && presentation.slides.getItem(index).shapes.items.length) continue;
    const slide = base(presentation, index);
    page(slide, index, index === 9);
    if (index === 1) {
      // Same location and typography as slide 2, preserving continuity.
      tarvo(slide, true);
    } else if (index === 2) {
      tarvo(slide, true);
      text(slide, 'opening-title', '3 frentes que\nnão se conectam', 88, 423, 580, 158, 48, { bold: true });
      triangle(slide, 0);
    } else if (index === 3) {
      tarvo(slide);
      const title = text(slide, 'opening-title', 'Planilha com\ntaxas e condições\nde cada lojista', 88, 245, 610, 280, 49);
      title.text.get('Planilha').bold = true;
      title.text.get('cada lojista').bold = true;
      triangle(slide, 1);
    } else if (index === 4) {
      tarvo(slide);
      const title = text(slide, 'opening-title', 'O que foi cobrado?', 90.38, 279, 610, 162, 48);
      title.text.get('cobrado').bold = true;
      triangle(slide, 2);
    } else if (index === 5) {
      tarvo(slide);
      const title = text(slide, 'opening-title', 'Entre pontas,\numa única pessoa', 88, 227, 570, 288, 62);
      title.text.get('única pessoa').bold = true;
      triangle(slide, 3);
    } else if (index >= 6 && index <= 8) {
      tarvo(slide);
      text(slide, 'opening-title', 'No fim do mês', 88, 145, 1100, 90, 60, { bold: true });
      const { helena } = triangle(slide, 3, true);
      const queries = ['Quanto pode faturar', 'O que precisa corrigir', 'Quais valores continuam\npendentes'];
      const available = index - 5;
      let last;
      for (let i = 0; i < available; i++) {
        const current = i === available - 1;
        last = text(slide, `closing-question-${i + 1}`, queries[i], 690, 298 + i * 114, 510, i === 2 ? 106 : 62, 37,
          { color: current ? palette.accent : palette.ink, bold: current });
      }
      if (last) {
        const target = presentation.resolve(last.toSnapshot().aid);
        connection(slide, helena, target, { fromSide: 'right', toSide: 'left', color: palette.accent, arrow: true });
      }
    } else if (index === 9) {
      slide.background.fill = palette.ink;
      text(slide, 'consequence-days', '8', 88, 122, 190, 238, 198, { color: palette.white, bold: true });
      text(slide, 'consequence-duration', 'dias úteis\npara fechar o mês', 306, 176, 850, 164, 55, { color: palette.white });
      text(slide, 'consequence-errors', 'Espaço para\ncobranças incorretas', 88, 457, 475, 120, 37, { color: '#A9D4BF' });
      text(slide, 'consequence-dependency', 'Fechamento dependente\nde quem conhece as regras', 650, 457, 548, 130, 37, { color: '#A9D4BF' });
    }
  }
}

export async function buildOpening({ presentation, input }) {
  if (input.phase === 'cover') await cover(presentation, input);
  else if (input.phase === 'develop') develop(presentation, input.indices);
  else if (input.phase !== 'inspect') throw new Error('Unknown presentation phase');
  if (input.render !== false) await presentation.render(input.phase === 'cover' ? { slide: 0 } : {});
  return {
    totalSlides: presentation.slides.items.length,
    slides: presentation.slides.items.map((slide, index) => ({
      index, topic: opening[index]?.[0], id: slide.toSnapshot().aid,
    })),
  };
}

export async function refineIntro({ presentation, input }) {
  for (const id of input.identificationIds) {
    const shape = presentation.resolve(id);
    shape.position = { left: 88, top: 236, width: 520, height: 132 };
    shape.text = 'Tarvo';
    shape.text.style = { typeface: 'Arial', fontSize: 104, bold: true, color: palette.ink,
      verticalAlignment: 'top', autoFit: 'none', wrap: 'none', insets: 0 };
  }
  const title = presentation.resolve(input.titleId);
  title.position = { left: 88, top: 423, width: 580, height: 158 };
  title.text = 'Três frentes que\nnão se conectam';
  title.text.style = { typeface: 'Arial', fontSize: 48, bold: true, color: palette.ink,
    verticalAlignment: 'top', autoFit: 'none', wrap: 'none', insets: 0 };
  await presentation.render({ slide: [1, 2] });
}
