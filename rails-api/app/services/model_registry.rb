# Yüklü modeli tutar: kaynaktan (ModelSource) çeker, tmp/model_cache'e yazar, ONNX oturumunu açar.
# Süreç başına tek kopya; #reload! yeni modeli hazırlayıp tek atamayla değiştirir (istekler kesilmez).
require "digest"

class ModelRegistry
  Loaded = Data.define(:config, :session, :source, :sha256, :loaded_at)

  class InvalidInput < StandardError
    attr_reader :details
    def initialize(details) = (@details = details; super("geçersiz girdi"))
  end

  class << self
    def instance = @instance ||= new
    delegate :current, :reload!, :predict, to: :instance
  end

  def initialize(source_factory = -> { ModelSource.from_env })
    @source_factory = source_factory
    @lock = Mutex.new
    @current = nil
  end

  # İlk istekte tembel yükleme (açılışta config/initializers/model.rb ön-yükler).
  def current = @current || @lock.synchronize { @current ||= load }

  def reload!
    yeni = load
    @lock.synchronize { @current = yeni }
  end

  def predict(inputs)
    m = current
    features = m.config.fetch("features")
    eksik = features.map { |f| f["name"] }.reject { |n| inputs.key?(n) }
    gecersiz = features.filter_map { |f| f["name"] if inputs.key?(f["name"]) && !sayi?(inputs[f["name"]]) }
    raise InvalidInput.new({ missing: eksik, invalid: gecersiz }) if eksik.any? || gecersiz.any?

    x = [features.map { |f| Float(inputs[f["name"]]) }]
    proba = m.session.predict({ "input" => x }, output_names: ["probabilities"])["probabilities"][0]
    labels = m.config.fetch("classes").map { |c| m.config.fetch("class_labels").fetch(c) }
    labels.zip(proba).to_h
  end

  private

  def sayi?(v) = Float(v, exception: false)&.finite? || false

  def load
    source = @source_factory.call
    config_bytes = source.fetch("config.json")
    onnx_bytes = source.fetch("model.onnx")
    sha = Digest::SHA256.hexdigest(onnx_bytes)

    # onnxruntime gem'i dosya yolundan yükler → içerik özetiyle adlandırılmış önbellek dosyası.
    dir = Rails.root.join("tmp/model_cache")
    FileUtils.mkdir_p(dir)
    path = dir.join("#{sha}.onnx")
    File.binwrite(path, onnx_bytes) unless path.exist?

    Loaded.new(config: JSON.parse(config_bytes), session: OnnxRuntime::Model.new(path.to_s),
               source: source.describe, sha256: sha, loaded_at: Time.current)
  end
end
