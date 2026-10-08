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

const timestampSuffix = new Date().toISOString().replace(/[-:T.]/g, '').slice(0, 14);
const zipFileName = `catos-frontend-local-resume-${timestampSuffix}.zip`;
const zipFilePath = path.join(outputDir, zipFileName);

// Exclude patterns
const excludeDirs = new Set(['node_modules', '.git', '.cache', '.vite', '.turbo', '.vscode', 'scratch', 'rebuilt-dist']);
const excludeFiles = new Set([
  '.env',
  '.env.local',
  '.env.production',
  'pack-file-list.txt',
  'source-manifest-sha256.json', // preserve original historical manifest
  `source-manifest-local-resume-${timestampSuffix}.json`
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

async function createPackage() {
  console.log('=== catos-frontend-return 打包作業開始 ===');
  console.log('來源目錄:', sourceDir);
  console.log('目標 ZIP:', zipFilePath);

  // 1. 取得檔案清單並保證 Entry 嚴格唯一
  const rawFiles = getFiles(sourceDir);
  const uniqueFilesSet = new Set(rawFiles);
  const relFiles = Array.from(uniqueFilesSet).sort();

  console.log(`掃描到 ${relFiles.length} 個待打包檔案 (已去重保證唯一性)。`);

  // 2. 計算來源檔案 SHA-256 清單 (排除清單自身與 ZIP，防止自引 hash 衝突)
  const manifest = {
    packageName: zipFileName,
    createdAt: new Date().toISOString(),
    sourceDir: 'frontend/redesign-v2-return',
    totalFiles: relFiles.length,
    files: {}
  };

  for (const rel of relFiles) {
    const fullPath = path.join(sourceDir, rel);
    const sha256 = calculateFileSha256(fullPath);
    manifest.files[rel] = sha256;
  }

  // 另存新清單檔案至 outputs/ 避免覆寫歷史清單
  const manifestOutPath = path.join(outputDir, `source-manifest-local-resume-${timestampSuffix}.json`);
  fs.writeFileSync(manifestOutPath, JSON.stringify(manifest, null, 2), 'utf-8');
  console.log('已產出來源檔案 SHA-256 清單 (另存新檔，不覆寫歷史):', manifestOutPath);

  // 3. 建立嚴格唯一臨時壓縮清單檔
  const fileListTxt = path.join(sourceDir, 'pack-file-list.txt');
  fs.writeFileSync(fileListTxt, relFiles.join('\n'), 'utf-8');

  // 4. 執行壓縮 (使用 tar -a -cf 保持精確性與一致性)
  if (fs.existsSync(zipFilePath)) {
    fs.unlinkSync(zipFilePath);
  }

  console.log('正在打包 ZIP (排除 node_modules, .git, 快取, 歷史 manifest)...');
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
  const containsPackageJson = zipContentLines.includes('package.json');
  const containsLockfile = zipContentLines.includes('package-lock.json');
  const containsSelfManifest = zipContentLines.some(l => l.includes(`source-manifest-local-resume-${timestampSuffix}.json`));

  console.log('- 排除 node_modules:', !containsNodeModules ? '✓ 正確排除' : '✗ 包含錯誤');
  console.log('- 排除 .git:', !containsGit ? '✓ 正確排除' : '✗ 包含錯誤');
  console.log('- 包含 src/:', containsSrc ? '✓ 正確包含' : '✗ 缺少');
  console.log('- 包含 package.json:', containsPackageJson ? '✓ 正確包含' : '✗ 缺少');
  console.log('- 包含 package-lock.json:', containsLockfile ? '✓ 正確包含' : '✗ 缺少');
  console.log('- 排除自身清單以避循環哈希矛盾:', !containsSelfManifest ? '✓ 正確排除' : '✗ 包含錯誤');
  console.log('- ZIP 條目完全唯一性:', duplicateEntries.length === 0 ? '✓ 嚴格唯一' : '✗ 存在重複');

  // 保存打包摘要資訊
  const summary = {
    zipPath: zipFilePath,
    zipFileName,
    zipSizeBytes: zipStat.size,
    zipSha256: zipSha256.toUpperCase(),
    filesCount: zipContentLines.length,
    manifestPath: manifestOutPath,
    verification: {
      excludedNodeModules: !containsNodeModules,
      excludedGit: !containsGit,
      hasSrc: containsSrc,
      hasPackageJson: containsPackageJson,
      hasLockfile: containsLockfile,
      excludedSelfManifest: !containsSelfManifest,
      entriesUnique: duplicateEntries.length === 0
    }
  };

  const summaryOut = path.join(outputDir, `catos-frontend-local-resume-${timestampSuffix}-summary.json`);
  fs.writeFileSync(summaryOut, JSON.stringify(summary, null, 2), 'utf-8');
  console.log('打包摘要已保存至:', summaryOut);
}

createPackage().catch(err => {
  console.error('打包失敗:', err);
  process.exit(1);
});
