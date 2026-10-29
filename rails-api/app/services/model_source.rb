# Model dosyalarının (config.json + model.onnx) NEREDEN okunacağı. Hepsi aynı arayüz: #fetch(ad) → bayt.
#
#   MODEL_SOURCE=local  MODEL_LOCAL_DIR=storage/models/hello
#   MODEL_SOURCE=http   MODEL_HTTP_BASE=https://huggingface.co/<repo>/resolve/main/  [MODEL_HTTP_TOKEN=hf_...]
#   MODEL_SOURCE=s3     MODEL_S3_BUCKET=... MODEL_S3_PREFIX=hello/ [MODEL_S3_REGION] [MODEL_S3_ENDPOINT]
#                       (+ AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY — aws-sdk'nın standart zinciri)
#
# MODEL_S3_ENDPOINT verilirse S3 uyumlu servis kullanılır (Hetzner Object Storage, MinIO, Cloudflare R2 ...).
require "net/http"

module ModelSource
  DEFAULT_HTTP_BASE = "https://huggingface.co/5eyyah/hello-diabetes-onnx/resolve/main/".freeze

  def self.from_env(env = ENV)
    case (env["MODEL_SOURCE"].presence || "http")
    when "local" then Local.new(env["MODEL_LOCAL_DIR"].presence || Rails.root.join("storage/models/hello").to_s)
    when "http"  then Http.new(env["MODEL_HTTP_BASE"].presence || DEFAULT_HTTP_BASE, token: env["MODEL_HTTP_TOKEN"].presence)
    when "s3"
      S3.new(bucket: env.fetch("MODEL_S3_BUCKET"), prefix: env["MODEL_S3_PREFIX"].to_s,
             region: env["MODEL_S3_REGION"].presence || "us-east-1", endpoint: env["MODEL_S3_ENDPOINT"].presence)
    else
      raise ArgumentError, "bilinmeyen MODEL_SOURCE=#{env['MODEL_SOURCE'].inspect} (local|http|s3)"
    end
  end

  class Local
    def initialize(dir) = @dir = dir
    def fetch(name) = File.binread(File.join(@dir, name))
    def describe = "local:#{@dir}"
  end

  class Http
    def initialize(base, token: nil)
      @base = base.end_with?("/") ? base : "#{base}/"
      @token = token
    end

    def fetch(name, uri = URI.join(@base, name), redirects = 5)
      req = Net::HTTP::Get.new(uri)
      # Token yalnız ilk host'a gider; yönlendirilen CDN'e (HF → cas-bridge vb.) sızdırılmaz.
      req["Authorization"] = "Bearer #{@token}" if @token && uri.host == URI(@base).host
      res = Net::HTTP.start(uri.host, uri.port, use_ssl: uri.scheme == "https", open_timeout: 10, read_timeout: 60) do |h|
        h.request(req)
      end
      case res
      when Net::HTTPSuccess then res.body
      when Net::HTTPRedirection
        raise "çok fazla yönlendirme: #{uri}" if redirects.zero?
        fetch(name, URI.join(uri, res["location"]), redirects - 1)
      else
        raise "#{uri} → HTTP #{res.code}"
      end
    end

    def describe = "http:#{@base}"
  end

  class S3
    def initialize(bucket:, prefix:, region:, endpoint:)
      require "aws-sdk-s3"
      @bucket, @prefix = bucket, prefix
      opts = { region: region }
      opts.merge!(endpoint: endpoint, force_path_style: true) if endpoint
      @client = Aws::S3::Client.new(**opts)
      @endpoint = endpoint
    end

    def fetch(name) = @client.get_object(bucket: @bucket, key: "#{@prefix}#{name}").body.read
    def put(name, bytes) = @client.put_object(bucket: @bucket, key: "#{@prefix}#{name}", body: bytes)
    def describe = "s3:#{@endpoint ? "#{@endpoint}/" : ''}#{@bucket}/#{@prefix}"
  end
end
