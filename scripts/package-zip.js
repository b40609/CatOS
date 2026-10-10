const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const crypto = require('crypto');

const repoRoot = path.resolve(__dirname, '..');
const srcDir = path.join(repoRoot, 'frontend/redesign-v1');
const stagingDir = path.join(repoRoot, 'frontend/_staging_redesign_v1');
const zipPath = path.join(repoRoot, 'frontend/catos-frontend-redesign-v1.zip');

// 排除規則
const EXCLUDE_DIRS = new Set(['node_modules', '.git']);
const EXCLUDE_EXTS = new Set(['.db', '.sqlite', '.sqlite3', '.wal', '.shm', '.key', '.pem', '.crt']);
const EXCLUDE_FILES = new Set(['.env', '.env.local', '.env.production']);

if (fs.existsSync(stagingDir)) {
  fs.rmSync(stagingDir, { recursive: true, force: true });
}
if (fs.existsSync(zipPath)) {
  fs.unlinkSync(zipPath);
}

fs.mkdirSync(stagingDir, { recursive: true });

let fileCount = 0;

function copyRecursive(src, dest) {
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);

    if (entry.isDirectory()) {
      if (EXCLUDE_DIRS.has(entry.name)) {
        continue;
      }
      fs.mkdirSync(destPath, { recursive: true });
      copyRecursive(srcPath, destPath);
    } else {
      const ext = path.extname(entry.name).toLowerCase();
      if (EXCLUDE_EXTS.has(ext) || EXCLUDE_FILES.has(entry.name)) {
        continue;
      }
      fs.copyFileSync(srcPath, destPath);
      fileCount++;
    }
  }
}

console.log('Copying files to staging directory...');
copyRecursive(srcDir, stagingDir);
console.log(`Copied ${fileCount} files to staging.`);

console.log('Compressing to zip via PowerShell Compress-Archive...');
const psCommand = `powershell -NoProfile -Command "Compress-Archive -Path '${stagingDir}\\*' -DestinationPath '${zipPath}' -Force"`;
execSync(psCommand, { stdio: 'inherit' });

console.log('Cleaning up staging directory...');
fs.rmSync(stagingDir, { recursive: true, force: true });

if (fs.existsSync(zipPath)) {
  const zipBuffer = fs.readFileSync(zipPath);
  const hash = crypto.createHash('sha256').update(zipBuffer).digest('hex');
  const size = zipBuffer.length;
  console.log('ZIP Package Created Successfully:');
  console.log(`  Path: ${zipPath}`);
  console.log(`  Size: ${size.toLocaleString()} bytes (${(size / 1024 / 1024).toFixed(2)} MB)`);
  console.log(`  SHA-256: ${hash}`);

  // 將結果記錄至 JSON
  const zipInfo = {
    zipPath: path.relative(repoRoot, zipPath).replace(/\\/g, '/'),
    fileCount: fileCount,
    sizeBytes: size,
    sizeMB: (size / 1024 / 1024).toFixed(2),
    sha256: hash,
    createdAt: new Date().toISOString()
  };
  fs.writeFileSync(path.join(repoRoot, 'frontend/zip-package-info.json'), JSON.stringify(zipInfo, null, 2), 'utf8');
} else {
  console.error('Failed to create ZIP package.');
  process.exit(1);
}
