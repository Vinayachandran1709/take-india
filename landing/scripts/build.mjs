import { mkdir, copyFile, writeFile } from 'node:fs/promises';
import { publicFiles } from '../server.mjs';
import { renderPublicConfig } from '../api-config.js';

// Validate before writing any output. Only this explicit public variable is embedded.
const config = renderPublicConfig(process.env.TYPEIN_API_BASE_URL ?? '');
const output = new URL('../dist/', import.meta.url);
await mkdir(output, { recursive: true });
for (const filename of publicFiles) {
  if (filename === 'config.js') {
    await writeFile(new URL(filename, output), config);
  } else {
    await copyFile(new URL(`../${filename}`, import.meta.url), new URL(filename, output));
  }
}
console.log(`Built ${publicFiles.length} static assets in landing/dist. No dependencies or external requests.`);
