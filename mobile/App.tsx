import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  useColorScheme,
  View,
} from 'react-native';

import defaults from './src/defaults.json';
import { apiYukle, gomuluYukle, tahmin, uzakYukle, YukluModel } from './src/model';

type Kaynak = 'gomulu' | 'uzak' | 'api';

const KAYNAK_ADI: Record<Kaynak, string> = {
  gomulu: 'Gömülü (çevrimdışı)',
  uzak: 'Uzak (Hugging Face)',
  api: 'Sunucu (kendi backend)',
};

export default function App() {
  const koyu = useColorScheme() === 'dark';
  const r = koyu ? koyuRenk : acikRenk;

  const [kaynak, setKaynak] = useState<Kaynak>('gomulu');
  const [repo, setRepo] = useState(defaults.modelRepo);
  const [apiUrl, setApiUrl] = useState(defaults.apiBaseUrl);
  const [model, setModel] = useState<YukluModel | null>(null);
  const [girdi, setGirdi] = useState<Record<string, string>>({});
  const [sonuc, setSonuc] = useState<Record<string, number> | null>(null);
  const [mesgul, setMesgul] = useState(false);
  const [hata, setHata] = useState<string | null>(null);

  async function yukle(k: Kaynak = kaynak, yenidenIndir = false) {
    setMesgul(true);
    setHata(null);
    setSonuc(null);
    try {
      const m =
        k === 'gomulu'
          ? await gomuluYukle()
          : k === 'uzak'
            ? await uzakYukle(repo.trim(), yenidenIndir)
            : await apiYukle(apiUrl.trim());
      setModel(m);
      setGirdi(Object.fromEntries(m.config.features.map((o) => [o.name, String(o.example)])));
    } catch (e) {
      setModel(null);
      setHata(`Model yüklenemedi: ${(e as Error).message}`);
    } finally {
      setMesgul(false);
    }
  }

  async function hesapla() {
    if (!model) return;
    const sayilar = Object.fromEntries(Object.entries(girdi).map(([k, v]) => [k, Number(v.replace(',', '.'))]));
    const gecersiz = Object.entries(sayilar).filter(([, v]) => !Number.isFinite(v)).map(([k]) => k);
    if (gecersiz.length) {
      setHata(`Geçersiz sayı: ${gecersiz.join(', ')}`);
      return;
    }
    setHata(null);
    try {
      setSonuc(await tahmin(model, sayilar));
    } catch (e) {
      setHata(`Tahmin hatası: ${(e as Error).message}`);
    }
  }

  // Açılışta gömülü modeli yükle → ağ olmadan da hemen kullanılabilir.
  useEffect(() => {
    yukle();
  }, []);

  return (
    <View style={[s.kok, { backgroundColor: r.bg }]}>
      <ScrollView contentContainerStyle={s.icerik} keyboardShouldPersistTaps="handled">
        <Text style={[s.baslik, { color: r.fg }]}>huggingface hello</Text>
        <Text style={[s.kucuk, { color: r.muted }]}>
          {model
            ? `Model: diabetes · AUC ${model.config.metrics.auc} · yalnız deneme amaçlı, klinik karar için kullanılmaz.\nKaynak: ${model.kaynak}`
            : 'Model yükleniyor…'}
        </Text>

        <View style={[s.kart, { backgroundColor: r.card, borderColor: r.line }]}>
          <Text style={[s.etiket, { color: r.muted }]}>Model kaynağı</Text>
          <View style={s.satir}>
            {(Object.keys(KAYNAK_ADI) as Kaynak[]).map((k) => (
              <Pressable
                key={k}
                onPress={() => {
                  setKaynak(k);
                  yukle(k);
                }}
                style={[s.secim, { borderColor: r.line }, kaynak === k && { backgroundColor: r.accent, borderColor: r.accent }]}
              >
                <Text style={{ color: kaynak === k ? '#fff' : r.fg }}>{KAYNAK_ADI[k]}</Text>
              </Pressable>
            ))}
          </View>
          {kaynak === 'uzak' && (
            <TextInput
              value={repo}
              onChangeText={setRepo}
              autoCapitalize="none"
              autoCorrect={false}
              placeholder="kullanıcı/model-repo"
              placeholderTextColor={r.muted}
              style={[s.girdi, { color: r.fg, borderColor: r.line, backgroundColor: r.bg }]}
            />
          )}
          {kaynak === 'api' && (
            <>
              <TextInput
                value={apiUrl}
                onChangeText={setApiUrl}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="url"
                placeholder="http://localhost:3100"
                placeholderTextColor={r.muted}
                style={[s.girdi, { color: r.fg, borderColor: r.line, backgroundColor: r.bg }]}
              />
              <Text style={[s.etiket, { color: r.muted }]}>
                USB/kablosuz adb ile: adb reverse tcp:3100 tcp:3100 → localhost. Aynı Wi-Fi: http://&lt;bilgisayar-IP&gt;:3100
              </Text>
            </>
          )}
          <View style={s.satir}>
            <Dugme yazi="Modeli yükle" onPress={() => yukle(kaynak, false)} renk={r.accent} pasif={mesgul} />
            {kaynak === 'uzak' && <Dugme yazi="Yeniden indir" onPress={() => yukle(kaynak, true)} renk={r.muted} pasif={mesgul} />}
            {mesgul && <ActivityIndicator color={r.accent} />}
          </View>
        </View>

        {model && (
          <View style={[s.kart, { backgroundColor: r.card, borderColor: r.line }]}>
            <View style={s.izgara}>
              {model.config.features.map((o) => (
                <View key={o.name} style={s.alan}>
                  <Text style={[s.etiket, { color: r.muted }]}>{o.label}</Text>
                  <TextInput
                    value={girdi[o.name] ?? ''}
                    onChangeText={(v) => setGirdi({ ...girdi, [o.name]: v })}
                    keyboardType="decimal-pad"
                    style={[s.girdi, { color: r.fg, borderColor: r.line, backgroundColor: r.bg }]}
                  />
                </View>
              ))}
            </View>
            <Dugme yazi="Tahmin et" onPress={hesapla} renk={r.accent} pasif={mesgul} />
          </View>
        )}

        {hata && <Text style={[s.kucuk, { color: r.bad }]}>{hata}</Text>}

        {sonuc && (
          <View style={[s.kart, { backgroundColor: r.card, borderColor: r.line }]}>
            {Object.entries(sonuc).map(([ad, p]) => (
              <View key={ad} style={s.cubukSatir}>
                <Text style={[s.cubukAd, { color: r.fg }]}>{ad}</Text>
                <View style={[s.iz, { backgroundColor: r.line }]}>
                  <View style={[s.dolgu, { width: `${p * 100}%`, backgroundColor: r.accent }]} />
                </View>
                <Text style={[s.yuzde, { color: r.fg }]}>{(p * 100).toFixed(1)}%</Text>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
      <StatusBar style={koyu ? 'light' : 'dark'} />
    </View>
  );
}

function Dugme({ yazi, onPress, renk, pasif }: { yazi: string; onPress: () => void; renk: string; pasif?: boolean }) {
  return (
    <Pressable onPress={onPress} disabled={pasif} style={[s.dugme, { backgroundColor: renk, opacity: pasif ? 0.5 : 1 }]}>
      <Text style={s.dugmeYazi}>{yazi}</Text>
    </Pressable>
  );
}

const acikRenk = { bg: '#f7f7f5', fg: '#1d1d1b', muted: '#6b6b66', card: '#ffffff', line: '#e2e2dc', accent: '#2f6fde', bad: '#c2410c' };
const koyuRenk = { bg: '#161615', fg: '#ececea', muted: '#9a9a94', card: '#1f1f1d', line: '#33332f', accent: '#6b9cf0', bad: '#f08a4b' };

const s = StyleSheet.create({
  kok: { flex: 1 },
  icerik: { padding: 16, paddingTop: 56, gap: 12 },
  baslik: { fontSize: 22, fontWeight: '600' },
  kucuk: { fontSize: 13, lineHeight: 18 },
  kart: { borderWidth: 1, borderRadius: 10, padding: 14, gap: 10 },
  etiket: { fontSize: 12 },
  satir: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, alignItems: 'center' },
  secim: { borderWidth: 1, borderRadius: 6, paddingVertical: 8, paddingHorizontal: 12 },
  girdi: { borderWidth: 1, borderRadius: 6, paddingVertical: 6, paddingHorizontal: 8, fontSize: 15 },
  izgara: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  alan: { width: '47%', gap: 4 },
  dugme: { borderRadius: 6, paddingVertical: 9, paddingHorizontal: 16, alignSelf: 'flex-start' },
  dugmeYazi: { color: '#fff', fontWeight: '600' },
  cubukSatir: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  cubukAd: { width: 100, fontSize: 13 },
  iz: { flex: 1, height: 10, borderRadius: 5, overflow: 'hidden' },
  dolgu: { height: '100%' },
  yuzde: { width: 52, textAlign: 'right', fontSize: 13 },
});
