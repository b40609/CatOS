const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const baseDir = path.resolve(__dirname, '../frontend/redesign-v1');
const repoRoot = path.resolve(__dirname, '..');

function getFiles(dir) {
  let results = [];
  const list = fs.readdirSync(dir);
  list.forEach(file => {
    const fullPath = path.join(dir, file);
    const stat = fs.statSync(fullPath);
    if (stat && stat.isDirectory()) {
      if (file !== 'node_modules' && file !== '.git') {
        results = results.concat(getFiles(fullPath));
      }
    } else {
      results.push(fullPath);
    }
  });
  return results;
}

const files = getFiles(baseDir);
const report = files.map(file => {
  const content = fs.readFileSync(file);
  const hash = crypto.createHash('sha256').update(content).digest('hex');
  const relPath = path.relative(repoRoot, file).replace(/\\/g, '/');
  return {
    path: relPath,
    hash: hash,
    size: content.length
  };
});

report.sort((a, b) => a.path.localeCompare(b.path));
fs.writeFileSync(path.resolve(repoRoot, 'redesign-v1-hashes.json'), JSON.stringify(report, null, 2), 'utf8');
console.log(`Generated hashes for ${report.length} files.`);
