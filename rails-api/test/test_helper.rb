ENV["RAILS_ENV"] ||= "test"
# Testler ağsız çalışır: modeli fixture klasöründen oku.
ENV["MODEL_SOURCE"] = "local"
ENV["MODEL_LOCAL_DIR"] = File.expand_path("fixtures/files/model", __dir__)
require_relative "../config/environment"
require "rails/test_help"

module ActiveSupport
  class TestCase
    # Run tests in parallel with specified workers
    parallelize(workers: :number_of_processors)

    # Add more helper methods to be used by all tests here...
  end
end
