Rails.application.routes.draw do
  get "up" => "rails/health#show", as: :rails_health_check

  namespace :api do
    namespace :v1 do
      resource :model, only: :show do
        post :reload
      end
      resources :predictions, only: :create
    end
  end
end
