import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { execSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const sourceDir = path.resolve(__dirname, '../');
const outputDir = path.resolve(__dirname, '../../outputs');
fs.mkdirSync(outputDir, { recursive: true });

const zipFileName = `catos-frontend-local-resume-20261005-r2.zip`;
const zipFilePath = path.join(outputDir, zipFileName);

// Exclude patterns
const excludeDirs = new Set(['node_modules', '.git', '.cache', '.vite', '.turbo', '.vscode', 'scratch']);
const excludeFiles = new Set([
  '.env',
  '.env.local',
  '.env.production',
  'pack-file-list.txt',
  'source-manifest-sha256.json',
  'source-manifest-local-resume-20261005-r2.json'
]);

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
      if (
        excludeFiles.has(dirent.name) ||
        dirent.name.endsWith('.tmp') ||
        dirent.name.endsWith('.zip')
      ) {
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

async function createPackageR2() {
  console.log('=== CatOS Frontend R2 打包作業開始 ===');
  console.log('來源目錄:', sourceDir);
  console.log('目標 ZIP:', zipFilePath);

  // 1. 取得檔案清單並保證 Entry 嚴格唯一
  const rawFiles = getFiles(sourceDir);
  const uniqueFilesSet = new Set(rawFiles);
  const relFiles = Array.from(uniqueFilesSet).sort();

  console.log(`掃描到 ${relFiles.length} 個待打包檔案 (已去重保證唯一性)。`);

  // 2. 計算來源與產物檔案 SHA-256 清單
  const manifest = {
    packageName: zipFileName,
    createdAt: new Date().toISOString(),
    sourceDir: 'frontend/redesign-v2-return',
    totalFiles: relFiles.length,
    distBuildHashes: {
      indexHtml: calculateFileSha256(path.join(sourceDir, 'dist/index.html')),
      jsBundle: calculateFileSha256(path.join(sourceDir, 'dist/assets/index-CoGYLu7B.js')),
      cssBundle: calculateFileSha256(path.join(sourceDir, 'dist/assets/index-C6c_wTSd.css'))
    },
    files: {}
  };

  for (const rel of relFiles) {
    const fullPath = path.join(sourceDir, rel);
    const sha256 = calculateFileSha256(fullPath);
    manifest.files[rel] = sha256;
  }

  // 另存新清單檔案至 outputs/ 避免覆寫歷史清單
  const manifestOutPath = path.join(outputDir, `source-manifest-local-resume-20261005-r2.json`);
  fs.writeFileSync(manifestOutPath, JSON.stringify(manifest, null, 2), 'utf-8');
  console.log('已產出來源檔案 SHA-256 清單 (另存新檔，不覆寫歷史):', manifestOutPath);

  // 3. 建立嚴格唯一臨時壓縮清單檔
  const fileListTxt = path.join(sourceDir, 'pack-file-list.txt');
  fs.writeFileSync(fileListTxt, relFiles.join('\n'), 'utf-8');

  // 4. 執行壓縮 (使用 tar -a -cf 保持精確性與一致性)
  if (fs.existsSync(zipFilePath)) {
    fs.unlinkSync(zipFilePath);
  }

  console.log('正在打包 ZIP (包含最新 dist/ 與 dist-local-resume-r2/, 排除 node_modules, .git, 快取)...');
  const tarCmd = `tar -a -cf "${zipFilePath}" -T "${fileListTxt}"`;
  execSync(tarCmd, { cwd: sourceDir, stdio: 'inherit' });

  // 清除暫存清單
  if (fs.existsSync(fileListTxt)) {
    fs.unlinkSync(fileListTxt);
  }

  // 5. 計算 ZIP SHA-256
  const zipSha256 = calculateFileSha256(zipFilePath);
  const zipStat = fs.statSync(zipFilePath);

  console.log('\n=== R2 打包完成 ===');
  console.log('ZIP 路徑:', zipFilePath);
  console.log('ZIP 大小:', `${(zipStat.size / (1024 * 1024)).toFixed(2)} MB (${zipStat.size} bytes)`);
  console.log('ZIP SHA-256:', zipSha256.toUpperCase());

  // 6. 核對驗證 ZIP 內容與唯一性
  console.log('\n正在檢查 ZIP 內容結構與條目唯一性...');
  const zipContentRaw = execSync(`tar -tf "${zipFilePath}"`, { encoding: 'utf-8' });
  const zipContentLines = zipContentRaw.split('\n').map(l => l.trim()).filter(Boolean);

  const duplicateEntries = zipContentLines.filter((item, index) => zipContentLines.indexOf(item) !== index);
  if (duplicateEntries.length > 0) {
    throw new Error(`ZIP 存在重複條目: ${duplicateEntries.join(', ')}`);
  }

  const containsNodeModules = zipContentLines.some(l => l.includes('node_modules'));
  const containsGit = zipContentLines.some(l => l.includes('.git'));
  const containsSrc = zipContentLines.some(l => l.startsWith('src/'));
  const containsDist = zipContentLines.some(l => l.startsWith('dist/'));
  const containsDistR2 = zipContentLines.some(l => l.startsWith('dist-local-resume-r2/'));
  const containsEvidenceR2 = zipContentLines.some(l => l.startsWith('evidence/local-resume-20261005-r2/'));
  const containsNewJsBundle = zipContentLines.includes('dist/assets/index-CoGYLu7B.js');
  const containsNewCssBundle = zipContentLines.includes('dist/assets/index-C6c_wTSd.css');
  const containsOldJsBundle = zipContentLines.includes('dist/assets/index-B7jkDTJG.js');

  console.log('- 排除 node_modules:', !containsNodeModules ? '✓ 正確排除' : '✗ 包含錯誤');
  console.log('- 排除 .git:', !containsGit ? '✓ 正確排除' : '✗ 包含錯誤');
  console.log('- 包含 src/:', containsSrc ? '✓ 正確包含' : '✗ 缺少');
  console.log('- 包含最新 dist/:', containsDist ? '✓ 正確包含' : '✗ 缺少');
  console.log('- 包含隔離快照 dist-local-resume-r2/:', containsDistR2 ? '✓ 正確包含' : '✗ 缺少');
  console.log('- 包含 R2 證據目錄:', containsEvidenceR2 ? '✓ 正確包含' : '✗ 缺少');
  console.log('- 包含最新 JS 建置產物 (index-CoGYLu7B.js):', containsNewJsBundle ? '✓ 正確包含' : '✗ 缺少');
  console.log('- 包含最新 CSS 建置產物 (index-C6c_wTSd.css):', containsNewCssBundle ? '✓ 正確包含' : '✗ 缺少');
  console.log('- 已清除歷史舊 JS 建置 (index-B7jkDTJG.js):', !containsOldJsBundle ? '✓ 正確排除舊版' : '✗ 殘留舊版');
  console.log('- ZIP 條目完全唯一性:', duplicateEntries.length === 0 ? '✓ 嚴格唯一' : '✗ 存在重複');

  // 保存打包摘要資訊
  const summary = {
    zipPath: zipFilePath,
    zipFileName,
    zipSizeBytes: zipStat.size,
    zipSha256: zipSha256.toUpperCase(),
    filesCount: zipContentLines.length,
    manifestPath: manifestOutPath,
    buildHashes: {
      indexHtml: manifest.distBuildHashes.indexHtml,
      jsBundle: manifest.distBuildHashes.jsBundle,
      cssBundle: manifest.distBuildHashes.cssBundle
    },
    verification: {
      excludedNodeModules: !containsNodeModules,
      excludedGit: !containsGit,
      hasSrc: containsSrc,
      hasDist: containsDist,
      hasDistR2: containsDistR2,
      hasEvidenceR2: containsEvidenceR2,
      hasLatestJsBundle: containsNewJsBundle,
      hasLatestCssBundle: containsNewCssBundle,
      excludedOldJsBundle: !containsOldJsBundle,
      entriesUnique: duplicateEntries.length === 0
    }
  };

  const summaryOut = path.join(outputDir, `catos-frontend-local-resume-20261005-r2-summary.json`);
  fs.writeFileSync(summaryOut, JSON.stringify(summary, null, 2), 'utf-8');
  console.log('R2 打包摘要已保存至:', summaryOut);
}

createPackageR2().catch(err => {
  console.error('R2 打包失敗:', err);
  process.exit(1);
});
