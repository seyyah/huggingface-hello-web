require "test_helper"

class PredictionsTest < ActionDispatch::IntegrationTest
  ORNEK = { pregnancies: 1, glucose: 193, blood_pressure: 50, skin_thickness: 16,
            insulin: 375, bmi: 25.9, pedigree: 0.655, age: 24 }.freeze

  test "GET /api/v1/model config ve kaynağı döner" do
    get "/api/v1/model"
    assert_response :success
    body = response.parsed_body
    assert_equal 8, body["config"]["features"].size
    assert_match(/\Alocal:/, body["source"])
  end

  test "POST /api/v1/predictions web/mobil/python ile aynı olasılığı verir" do
    post "/api/v1/predictions", params: { inputs: ORNEK }, as: :json
    assert_response :success
    body = response.parsed_body
    assert_in_delta 0.6771, body["proba"]["diabetes var"], 1e-4
    assert_equal "diabetes var", body["label"]
  end

  test "eksik ve sayı olmayan alanlar 422 döner" do
    post "/api/v1/predictions", params: { inputs: ORNEK.except(:age).merge(glucose: "abc") }, as: :json
    assert_response :unprocessable_content
    assert_equal ["age"], response.parsed_body["missing"]
    assert_equal ["glucose"], response.parsed_body["invalid"]
  end

  test "inputs yoksa 400 döner" do
    post "/api/v1/predictions", params: {}, as: :json
    assert_response :bad_request
  end
end
