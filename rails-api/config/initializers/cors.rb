# Web sayfası (GitHub Pages / yerel) API'yi tarayıcıdan çağırabilsin. Mobil uygulama CORS'a tabi değil.
# ŞİMDİLİK her origin serbest (auth yok); üretimde CORS_ORIGINS ile daraltın.
Rails.application.config.middleware.insert_before 0, Rack::Cors do
  allow do
    origins(*(ENV["CORS_ORIGINS"].presence&.split(",") || ["*"]))
    resource "/api/*", headers: :any, methods: %i[get post options]
  end
end
