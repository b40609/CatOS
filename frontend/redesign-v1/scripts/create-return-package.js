import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const sourceDir = path.resolve(__dirname, '../');
const outputDir = path.resolve(__dirname, '../../');
const zipFileName = 'catos-frontend-return-20261005-v2.zip';
const zipFilePath = path.join(outputDir, zipFileName);

// Exclude patterns
const excludeDirs = new Set(['node_modules', '.git', '.cache', '.vite', '.turbo', '.vscode', 'scratch']);
const excludeFiles = new Set(['.env', '.env.local', '.env.production']);

function getFiles(dir, baseDir = dir) {
  let results = [];
  const list = fs.readdirSync(dir, { withFileTypes: true });

  for (const dirent of list) {
    const fullPath = path.join(dir, dirent.name);
    const relPath = path.relative(baseDir, fullPath).replace(/\\/g, '/');

    if (dirent.isDirectory()) {
      if (excludeDirs.has(dirent.name)) {
        continue;
      }
      results = results.concat(getFiles(fullPath, baseDir));
    } else {
      if (excludeFiles.has(dirent.name) || dirent.name.endsWith('.tmp')) {
        continue;
      }
      results.push(relPath);
    }
  }
  return results;
}

function calculateFileSha256(filePath) {
  const fileBuffer = fs.readFileSync(filePath);
  const hashSum = crypto.createHash('sha256');
  hashSum.update(fileBuffer);
  return hashSum.digest('hex');
}

async function createPackage() {
  console.log('=== catos-frontend-return 打包作業開始 ===');
  console.log('來源目錄:', sourceDir);
  console.log('目標 ZIP:', zipFilePath);

  // 1. 取得檔案清單
  const relFiles = getFiles(sourceDir);
  console.log(`掃描到 ${relFiles.length} 個待打包檔案。`);

  // 2. 計算來源檔案 SHA-256 清單
  const manifest = {
    packageName: zipFileName,
    createdAt: new Date().toISOString(),
    sourceDir: 'frontend/redesign-v1',
    totalFiles: relFiles.length,
    files: {}
  };

  for (const rel of relFiles) {
    const fullPath = path.join(sourceDir, rel);
    const sha256 = calculateFileSha256(fullPath);
    manifest.files[rel] = sha256;
  }

  // 寫入清單檔案到原始目錄供打包
  const manifestPath = path.join(sourceDir, 'source-manifest-sha256.json');
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), 'utf-8');
  console.log('已產出來源檔案 SHA-256 清單:', manifestPath);

  // 包含自身
  relFiles.push('source-manifest-sha256.json');
  manifest.files['source-manifest-sha256.json'] = calculateFileSha256(manifestPath);

  // 3. 建立臨時臨時壓縮清單檔
  const fileListTxt = path.join(sourceDir, 'pack-file-list.txt');
  fs.writeFileSync(fileListTxt, relFiles.join('\n'), 'utf-8');

  // 4. 執行壓縮 (使用 bsdtar 保持精確性)
  if (fs.existsSync(zipFilePath)) {
    fs.unlinkSync(zipFilePath);
  }

  console.log('正在打包 ZIP (排除 node_modules, .git, 快取)...');
  // 使用 tar 建立 zip
  const tarCmd = `tar -a -cf "${zipFilePath}" -T "${fileListTxt}"`;
  execSync(tarCmd, { cwd: sourceDir, stdio: 'inherit' });

  // 清除暫存清單
  if (fs.existsSync(fileListTxt)) {
    fs.unlinkSync(fileListTxt);
  }

  // 5. 計算 ZIP SHA-256
  const zipSha256 = calculateFileSha256(zipFilePath);
  const zipStat = fs.statSync(zipFilePath);

  console.log('\n=== 打包完成 ===');
  console.log('ZIP 路徑:', zipFilePath);
  console.log('ZIP 大小:', `${(zipStat.size / (1024 * 1024)).toFixed(2)} MB (${zipStat.size} bytes)`);
  console.log('ZIP SHA-256:', zipSha256.toUpperCase());

  // 6. 核對驗證 ZIP 內容
  console.log('\n正在檢查 ZIP 內容結構...');
  const zipContentRaw = execSync(`tar -tf "${zipFilePath}"`, { encoding: 'utf-8' });
  const zipContentLines = zipContentRaw.split('\n').map(l => l.trim()).filter(Boolean);

  const containsNodeModules = zipContentLines.some(l => l.includes('node_modules'));
  const containsGit = zipContentLines.some(l => l.includes('.git'));
  const containsSrc = zipContentLines.some(l => l.startsWith('src/'));
  const containsPackageJson = zipContentLines.includes('package.json');
  const containsLockfile = zipContentLines.includes('package-lock.json');
  const containsHandoff = zipContentLines.some(l => l.includes('frontend-return-handoff.md'));
  const containsEvidence = zipContentLines.some(l => l.startsWith('evidence/'));

  console.log('- 排除 node_modules:', !containsNodeModules ? '✓ 正確排除' : '✗ 包含錯誤');
  console.log('- 排除 .git:', !containsGit ? '✓ 正確排除' : '✗ 包含錯誤');
  console.log('- 包含 src/:', containsSrc ? '✓ 正確包含' : '✗ 缺少');
  console.log('- 包含 package.json:', containsPackageJson ? '✓ 正確包含' : '✗ 缺少');
  console.log('- 包含 package-lock.json:', containsLockfile ? '✓ 正確包含' : '✗ 缺少');
  console.log('- 包含交接文件:', containsHandoff ? '✓ 正確包含' : '✗ 缺少');
  console.log('- 包含測試證據 evidence/:', containsEvidence ? '✓ 正確包含' : '✗ 缺少');

  // 保存打包摘要資訊
  const summary = {
    zipPath: zipFilePath,
    zipFileName,
    zipSizeBytes: zipStat.size,
    zipSha256: zipSha256.toUpperCase(),
    filesCount: zipContentLines.length,
    verification: {
      excludedNodeModules: !containsNodeModules,
      excludedGit: !containsGit,
      hasSrc: containsSrc,
      hasPackageJson: containsPackageJson,
      hasLockfile: containsLockfile,
      hasHandoff: containsHandoff,
      hasEvidence: containsEvidence
    }
  };

  const summaryOut = path.join(outputDir, 'catos-frontend-return-summary.json');
  fs.writeFileSync(summaryOut, JSON.stringify(summary, null, 2), 'utf-8');
  console.log('打包摘要已保存至:', summaryOut);
}

createPackage().catch(err => {
  console.error('打包失敗:', err);
  process.exit(1);
});
