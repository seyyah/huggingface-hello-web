# Modeli açılışta yükle → ilk istek beklemesin, yanlış kaynak ayarı hemen görünsün.
# Testlerde ve rake görevlerinde atlanır (MODEL_EAGER_LOAD=0 ile kapatılabilir).
Rails.application.config.after_initialize do
  next if Rails.env.test? || defined?(Rake.application) && Rake.application.top_level_tasks.any?
  next if ENV["MODEL_EAGER_LOAD"] == "0"

  m = ModelRegistry.current
  Rails.logger.info("[model] yüklendi: #{m.source} sha256=#{m.sha256[0, 12]}")
end
