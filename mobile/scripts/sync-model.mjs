// Gömülü modeli HF'den çeker: assets/model/{model.onnx,config.json}
// Kullanım: npm run sync-model [-- <hf-kullanıcı/repo>]   (varsayılan: src/defaults.json → modelRepo)
import { readFileSync, writeFileSync } from "node:fs";

const kok = new URL("..", import.meta.url);
const varsayilan = JSON.parse(readFileSync(new URL("src/defaults.json", kok))).modelRepo;
const repo = process.argv[2] || varsayilan;
const taban = `https://huggingface.co/${repo}/resolve/main/`;

for (const ad of ["config.json", "model.onnx"]) {
  const yanit = await fetch(taban + ad);
  if (!yanit.ok) throw new Error(`${taban + ad} → HTTP ${yanit.status}`);
  const veri = Buffer.from(await yanit.arrayBuffer());
  writeFileSync(new URL(`assets/model/${ad}`, kok), veri);
  console.log(`✓ ${ad} (${veri.length} B) ← ${repo}`);
}
