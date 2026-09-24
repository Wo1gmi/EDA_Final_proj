import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import JSZip from 'jszip';
import { FileBlob, PresentationFile } from '@oai/artifact-tool';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, '..');
const input = process.env.SLIDE_TEMPLATE || path.join(here, 'presentation.pptx');
const build = path.resolve(process.env.SLIDE_BUILD_DIR || path.join(repo, '.slides-build'));
const output = path.resolve(process.env.SLIDE_OUTPUT || path.join(build, 'presentation.pptx'));
const skill = process.env.PRESENTATIONS_SKILL_DIR;
const python = process.env.RUNTIME_PYTHON || 'python3';
if (!skill) throw new Error('Set PRESENTATIONS_SKILL_DIR to the installed Presentations skill directory.');
const { makeNativeBulletParagraphs, finalizePresentation } = await import(pathToFileURL(path.join(skill, 'container_tools/artifact_tool_utils.mjs')).href);
execFileSync(python, [path.join(here, 'prepare_content.py')], { cwd: repo, stdio: 'inherit' });
const content = JSON.parse(await fs.readFile(path.join(here, 'slide_content.json'), 'utf8'));
if (!Object.keys(content.inputs_sha256 || {}).length) throw new Error('Missing source checksums in slide_content.json.');
for (const [relative, expected] of Object.entries(content.inputs_sha256)) {
  const bytes = await fs.readFile(path.join(repo, relative));
  const actual = crypto.createHash('sha256').update(bytes).digest('hex');
  if (actual !== expected) throw new Error(`Results changed: ${relative}. Update slide_content.json from the current analysis outputs.`);
}
await fs.mkdir(build, { recursive: true });
await fs.mkdir(path.dirname(output), { recursive: true });
const source = await fs.readFile(input);
const sourceSha = crypto.createHash('sha256').update(source).digest('hex');
const p = await PresentationFile.importPptx(await FileBlob.load(input));
const before = await p.inspect({ kind: 'slide,textbox,shape,image,table,notes,layout', maxChars: 200000 });
const records = before.ndjson.split('\n').filter(Boolean).map(x => JSON.parse(x));
function target(kind, slide, name) {
  const found = records.filter(x => x.kind === kind && x.slide === slide && x.name === name);
  if (found.length !== 1) throw new Error(`Expected one ${kind} on slide ${slide} named ${name}.`);
  return p.resolve(found[0].id);
}
for (const item of content.text) {
  const s = target('textbox', item.slide, item.name);
  s.text = Array.isArray(item.text) ? makeNativeBulletParagraphs(item.text, { marginLeftPoints: 14, hangingPoints: 8, spaceAfterPoints: 12 }) : item.text;
  s.text.style = { typeface: 'Calibri', autoFit: 'none', wrap: 'square', verticalAlignment: 'top', insets: { left: 0, right: 0, top: 0, bottom: 0 }, ...item.style };
  if (item.position) s.position = item.position;
}
for (const item of content.tables) {
  const t = target('table', item.slide, item.name);
  for (let r = 0; r < item.values.length; r++) {
    for (let c = 0; c < item.values[r].length; c++) {
      t.cells.set(r, c, item.values[r][c]);
      t.getCell(r, c).text.style = { typeface: 'Calibri', fontSize: item.fontSize || 16, color: r ? '#1C2733' : '#FFFFFF', bold: r === 0, verticalAlignment: 'middle' };
    }
  }
}
for (const item of content.images) {
  const image = target('image', item.slide, item.name);
  const frame = item.position || image.frame;
  image.replace({ blob: new Uint8Array(await fs.readFile(path.join(repo, item.file))), contentType: 'image/png', alt: item.alt, fit: 'contain' });
  image.frame = frame;
  image.crop = { left: 0, top: 0, right: 0, bottom: 0 };
}
for (let i = 0; i < p.slides.items.length; i++) {
  p.slides.items[i].speakerNotes.textFrame.setText(content.notes[i]);
}
const candidate = path.join(build, 'candidate.pptx');
await (await PresentationFile.exportPptx(p)).save(candidate);
const zip = await JSZip.loadAsync(await fs.readFile(candidate));
let core = await zip.file('docProps/core.xml').async('string');
const escape = x => x.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
for (const [tag, value] of [['dc:creator', content.authors.join(', ')], ['lastModifiedBy', content.authors.join(', ')], ['dc:title', 'Ставка ЦБ, курс рубля и его волатильность']]) {
  const regex = new RegExp(`<${tag}[^>]*>[\\s\\S]*?<\\/${tag}>`);
  core = regex.test(core) ? core.replace(regex, `<${tag}>${escape(value)}</${tag}>`) : core.replace('</coreProperties>', `<${tag}>${escape(value)}</${tag}></coreProperties>`);
}
zip.file('docProps/core.xml', core);
for (const name of Object.keys(zip.files).filter(x => x.endsWith('.xml'))) {
  const xml = await zip.file(name).async('string');
  if (/[\u2013\u2014]/u.test(xml)) zip.file(name, xml.replace(/[\u2013\u2014]/gu, '-'));
}
await fs.writeFile(candidate, await zip.generateAsync({ type: 'nodebuffer' }));
const final = await finalizePresentation({
  workspaceDir: path.resolve(repo, '..'), candidatePath: candidate, finalPath: output,
  pythonExecutable: python,
  integrityValidatorPath: path.join(skill, 'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath: path.join(skill, 'container_tools/inspect_presentation_layout_geometry.py'),
  explicitTotalSlideCount: 11,
  requiredNativeTableOwnerSlides: [6, 8],
  requiredNativeChartOwnerSlides: [],
  layoutArgs: ['--expected-slide-size-emu', '12192000,6858000', '--validate-bullet-geometry', '--validate-heading-fit', '--require-native-table-slide', '6', '--require-native-table-slide', '8'],
  fontPolicy: { basis: 'reference', families: ['Calibri', 'Cambria'], referencePath: input, referenceSha256: sourceSha },
  verifyArtifactToolImport: true,
  receiptPath: path.join(build, 'validation.json')
});
const after = await p.inspect({ kind: 'slide,textbox,table,image,notes', maxChars: 200000 });
await fs.writeFile(path.join(build, 'inspect.ndjson'), after.ndjson);
for (let i = 0; i < p.slides.items.length; i++) {
  const image = await p.slides.items[i].export({ format: 'png', scale: 1 });
  await fs.writeFile(path.join(build, `slide-${i + 1}.png`), new Uint8Array(await image.arrayBuffer()));
}
console.log(JSON.stringify(final));
