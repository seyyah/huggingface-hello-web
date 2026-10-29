module Api
  module V1
    # POST /api/v1/predictions   {"inputs": {"glucose": 148, ...}}
    #   200 → {"proba": {"diabetes var": 0.67, ...}, "label": "diabetes var", "model": {...}}
    #   422 → {"error": "geçersiz girdi", "missing": [...], "invalid": [...]}
    class PredictionsController < ApplicationController
      def create
        inputs = params.require(:inputs).permit!.to_h
        proba = ModelRegistry.predict(inputs)
        m = ModelRegistry.current
        render json: { proba: proba, label: proba.max_by { |_, p| p }.first,
                       model: { source: m.source, sha256: m.sha256 } }
      rescue ModelRegistry::InvalidInput => e
        render json: { error: e.message, **e.details }, status: :unprocessable_content
      end
    end
  end
end
