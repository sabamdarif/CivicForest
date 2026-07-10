const fs = require('fs');
const path = require('path');

const libDir = path.join(__dirname, 'node_modules', 'typescript', 'lib');

if (fs.existsSync(libDir)) {
  // Patch version.cjs (CommonJS)
  const versionCjsPath = path.join(libDir, 'version.cjs');
  if (fs.existsSync(versionCjsPath)) {
    const versionCjsContent = `const tsStandard = require('typescript-standard');
Object.assign(exports, tsStandard);
exports.version = require("../package.json").version;
exports.versionMajorMinor = "7.0";
`;
    fs.writeFileSync(versionCjsPath, versionCjsContent, 'utf8');
    console.log('Successfully patched version.cjs!');
  }

  // Create lib/typescript.js (ES Module because package.json specifies "type": "module")
  const typescriptJsPath = path.join(libDir, 'typescript.js');
  const typescriptJsContent = `export * from 'typescript-standard';
export const version = "7.0.2";
export const versionMajorMinor = "7.0";
`;
  fs.writeFileSync(typescriptJsPath, typescriptJsContent, 'utf8');
  console.log('Successfully created lib/typescript.js!');
} else {
  console.warn('typescript lib directory not found at:', libDir);
}
