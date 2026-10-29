namespace :model do
  desc "Modeli yerel klasörden S3'e yükle: rails model:push_s3 DIR=../_out/model (hedef: MODEL_S3_* env)"
  task push_s3: :environment do
    dir = ENV.fetch("DIR", "../_out/model")
    s3 = ModelSource::S3.new(bucket: ENV.fetch("MODEL_S3_BUCKET"), prefix: ENV["MODEL_S3_PREFIX"].to_s,
                             region: ENV["MODEL_S3_REGION"].presence || "us-east-1", endpoint: ENV["MODEL_S3_ENDPOINT"].presence)
    %w[config.json model.onnx].each do |ad|
      s3.put(ad, File.binread(File.join(dir, ad)))
      puts "✓ #{ad} → #{s3.describe}#{ad}"
    end
  end

  desc "Kaynağı (MODEL_SOURCE env) dene ve örnek satırla tahmin yap"
  task check: :environment do
    m = ModelRegistry.current
    ornek = m.config["features"].to_h { |f| [f["name"], f["example"]] }
    puts({ source: m.source, sha256: m.sha256, proba: ModelRegistry.predict(ornek) }.to_json)
  end
end
