// onnxruntime-react-native, eski bir `unimodule.json` taşıdığı için Expo autolinking onu
// "Expo modülü" sanıyor ve RN autolinking'den düşürüyor; o da gerçek bir Expo modülü olmadığı
// için hiçbir yerde kaydedilmiyor → açılışta "Cannot read property 'install' of null" crash'i.
// Platformları açıkça vermek, onu klasik RN native modülü olarak linklenmeye zorlar.
module.exports = {
  dependencies: {
    'onnxruntime-react-native': {
      platforms: { android: {}, ios: {} },
    },
  },
};
