// Writes tools/art/cell.svg: my cell from StudySync, holding a magnifying glass, for the banner.
//
// It needs StudySync's frontend (private), so it only runs on a machine with a checkout:
//   node <frontend>/node_modules/jiti/lib/jiti-cli.mjs tools/art/export_cell.ts <frontend>
// The look is tools/art/cell.json; change it there and run this again, then python3 tools/banner.py.
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const frontend = process.argv[2];
if (!frontend) throw new Error('usage: export_cell.ts <path to StudySync frontend>');

const { cellSvg, parseCellLook } = await import(join(frontend, 'lib/character/cell.ts'));
await import(join(frontend, 'lib/character/wear/index.ts'));

const look = parseCellLook(JSON.parse(readFileSync(join(here, 'cell.json'), 'utf8')));
if (!look) throw new Error('cell.json is not a valid cell look');
// 'hold' with the magnifier in the right hand; the pupils turned a little toward the lens
const svg = cellSvg(look, 'hold', 'jt', { held: { key: 'magnifier' } }, { look: [3, 1] });
writeFileSync(join(here, 'cell.svg'), svg + '\n');
console.log(`wrote ${join(here, 'cell.svg')} (${svg.length} bytes)`);
