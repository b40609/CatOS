// Guard: app code must use the terminal type scale (text-t1..t4) or Tailwind's
// named sizes. Any arbitrary font-size utility (text-[10px], text-[0.7rem], ...)
// fails the check. Run via `npm run check:tokens`; `npm test` runs it first.
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const TARGETS = ['src', 'index.html'];
const FILE_RE = /\.(tsx?|jsx?|css|html)$/;
const ARBITRARY_FONT_SIZE = /text-\[[0-9.]+(?:px|rem|em)\]/g;

function* files(path) {
  for (const entry of readdirSync(path, { withFileTypes: true })) {
    const full = join(path, entry.name);
    if (entry.isDirectory()) yield* files(full);
    else if (FILE_RE.test(entry.name)) yield full;
  }
}

const hits = [];
for (const target of TARGETS) {
  const full = join(ROOT, target);
  const list = target.endsWith('.html') ? [full] : [...files(full)];
  for (const file of list) {
    const rel = relative(ROOT, file).split(sep).join('/');
    readFileSync(file, 'utf8').split('\n').forEach((line, i) => {
      for (const match of line.matchAll(ARBITRARY_FONT_SIZE)) hits.push(`${rel}:${i + 1}: ${match[0]}`);
    });
  }
}

if (hits.length) {
  console.error(`check:tokens FAILED - ${hits.length} arbitrary font size(s); use text-t1..t4 (9/10/11/12px) or a named size:`);
  for (const hit of hits) console.error('  ' + hit);
  process.exit(1);
}
console.log('check:tokens OK - no arbitrary font sizes in src/ or index.html');
