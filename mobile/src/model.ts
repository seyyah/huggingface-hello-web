// Model yükleme + tahmin. Üç kaynak:
//   - gömülü : uygulamayla paketlenen assets/model/{model.onnx,config.json} (çevrimdışı çalışır)
//   - uzak   : Hugging Face reposundan indirilir, cihazda önbelleğe alınır (yeni model = uygulama güncellemesi gerekmez)
//   - api    : kendi backend'imiz (../rails-api) hesaplar; model cihaza hiç inmez
// Sözleşme web sayfasıyla aynı: girdi "input" float32 [1, özellik], çıktı "probabilities" [1, sınıf].
import { Asset } from 'expo-asset';
import { Directory, File, Paths } from 'expo-file-system';
import { InferenceSession, Tensor } from 'onnxruntime-react-native';

import gomuluConfig from '../assets/model/config.json';

export type ModelConfig = {
  title: string;
  description: string;
  target: string;
  classes: string[];
  class_labels: Record<string, string>;
  features: { name: string; label: string; example: number }[];
  metrics: Record<string, number>;
};

// Cihazda çalışan ONNX oturumu ya da hesaplamayı yapan kendi backend'imiz (rails-api).
export type YukluModel =
  | { tur: 'onnx'; session: InferenceSession; config: ModelConfig; kaynak: string }
  | { tur: 'api'; baseUrl: string; config: ModelConfig; kaynak: string };

async function oturumAc(onnxUri: string): Promise<InferenceSession> {
  // Dosyayı bayt olarak okuyup veriyoruz → file:// / content:// yol farklarından bağımsız.
  const baytlar = await new File(onnxUri).bytes();
  return InferenceSession.create(baytlar);
}

export async function gomuluYukle(): Promise<YukluModel> {
  const asset = Asset.fromModule(require('../assets/model/model.onnx'));
  await asset.downloadAsync();
  if (!asset.localUri) throw new Error('gömülü model.onnx bulunamadı');
  return { tur: 'onnx', session: await oturumAc(asset.localUri), config: gomuluConfig as ModelConfig, kaynak: 'gömülü' };
}

function onbellekKlasoru(repo: string): Directory {
  const klasor = new Directory(Paths.document, 'models', repo.replace('/', '__'));
  klasor.create({ intermediates: true, idempotent: true });
  return klasor;
}

export async function uzakYukle(repo: string, yenidenIndir = false): Promise<YukluModel> {
  const klasor = onbellekKlasoru(repo);
  const config = new File(klasor, 'config.json');
  const model = new File(klasor, 'model.onnx');
  const onbellekte = config.exists && model.exists && !yenidenIndir;
  if (!onbellekte) {
    const taban = `https://huggingface.co/${repo}/resolve/main/`;
    await File.downloadFileAsync(taban + 'config.json', config, { idempotent: true });
    await File.downloadFileAsync(taban + 'model.onnx', model, { idempotent: true });
  }
  return {
    tur: 'onnx',
    session: await oturumAc(model.uri),
    config: JSON.parse(await config.text()) as ModelConfig,
    kaynak: `HF ${repo}${onbellekte ? ' (önbellek)' : ' (indirildi)'}`,
  };
}

async function jsonIstek(url: string, init?: RequestInit) {
  const yanit = await fetch(url, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } });
  const govde = await yanit.json().catch(() => ({}));
  if (!yanit.ok) throw new Error(`${url} → HTTP ${yanit.status} ${JSON.stringify(govde)}`);
  return govde;
}

// Model cihaza inmez: form şeması GET /api/v1/model'den, tahmin POST /api/v1/predictions'tan.
export async function apiYukle(baseUrl: string): Promise<YukluModel> {
  const kok = baseUrl.replace(/\/+$/, '');
  const bilgi = await jsonIstek(`${kok}/api/v1/model`);
  return { tur: 'api', baseUrl: kok, config: bilgi.config as ModelConfig, kaynak: `API ${kok} ← ${bilgi.source}` };
}

export async function tahmin(m: YukluModel, girdi: Record<string, number>): Promise<Record<string, number>> {
  if (m.tur === 'api') {
    const yanit = await jsonIstek(`${m.baseUrl}/api/v1/predictions`, { method: 'POST', body: JSON.stringify({ inputs: girdi }) });
    return yanit.proba as Record<string, number>;
  }
  const { features, classes, class_labels } = m.config;
  const x = new Tensor('float32', Float32Array.from(features.map((o) => girdi[o.name])), [1, features.length]);
  const cikti = await m.session.run({ input: x });
  const p = Array.from(cikti.probabilities.data as Float32Array);
  return Object.fromEntries(classes.map((c, i) => [class_labels[c], p[i]]));
}
