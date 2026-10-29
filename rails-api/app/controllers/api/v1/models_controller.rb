module Api
  module V1
    # GET  /api/v1/model         → yüklü modelin config'i + kaynağı (istemci formu bundan üretir)
    # POST /api/v1/model/reload  → modeli kaynaktan yeniden çek (ŞİMDİLİK auth yok — üretimde korunmalı)
    class ModelsController < ApplicationController
      def show
        render json: model_json(ModelRegistry.current)
      end

      def reload
        render json: model_json(ModelRegistry.reload!)
      end

      private

      def model_json(m)
        { config: m.config, source: m.source, sha256: m.sha256, loaded_at: m.loaded_at }
      end
    end
  end
end
