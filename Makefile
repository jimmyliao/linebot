# Makefile

PROJECT_ID := $(shell cat .env | grep GOOGLE_PROJECT_ID | cut -d'=' -f2)
REGION := $(shell cat .env | grep GOOGLE_LOCATION | cut -d'=' -f2)
SERVICE_NAME := $(shell cat .env | grep GOOGLE_SERVICE_NAME | cut -d'=' -f2)
IMAGE_NAME := gcr.io/$(PROJECT_ID)/$(SERVICE_NAME)
NGROK_TOKEN := $(shell cat .env | grep NGROK_TOKEN | cut -d'=' -f2)
TARGET_PLATFORM := linux/amd64

# Local run
local-tunnel:
	ngrok http 8080 --config .ngrok/config.yml

local:
	python app.py

# Local ACT to simulate GitHub Actions
local-act:
	act --container-architecture $(TARGET_PLATFORM) -j lint

# Build Docker image
build:
	docker buildx build --platform $(TARGET_PLATFORM) -t $(IMAGE_NAME) .

init:
	@if grep -Eq "^GEMINI_API_KEY=your_" .env && grep -Eq "^LINE_CHANNEL_ACCESS_TOKEN=your_" .env && grep -Eq "^LINE_CHANNEL_SECRET=your_" .env && grep -Eq "^GOOGLE_PROJECT_ID=your_" .env && grep -Eq "^GOOGLE_LOCATION=your_" .env && grep -Eq "^GOOGLE_SERVICE_NAME=your_" .env && grep -Eq "^NGROK_TOKEN=your_" .env; then echo "Error: Please update the .env file with your actual values." && exit 1; fi
	@set NGROK_TOKEN := $(shell grep NGROK_TOKEN .env | cut -d'=' -f2 | tr -d '\n')
	@echo ${NGROK_TOKEN}
	@cd $(CURDIR)
	@perl -pi -e "s/_TOKEN_/$(NGROK_TOKEN)/g" .ngrok/config.yml
	@cat .env

# Push Docker image to Google Container Registry
push:
	docker push $(IMAGE_NAME)

# Deploy to Cloud Run
deploy:
	gcloud config set project $(PROJECT_ID)
	gcloud config set run/region $(REGION)
	gcloud run deploy $(SERVICE_NAME) --image $(IMAGE_NAME) --platform managed --region $(REGION) --allow-unauthenticated

# Clean up Docker images (optional)
clean:
	docker rmi $(IMAGE_NAME)

run:
	docker run --env PORT=8080 --env NGROK_TOKEN=$(NGROK_TOKEN) --env-file .env -p 8080:8080 $(IMAGE_NAME)

destroy:
	gcloud run services delete $(SERVICE_NAME) --region $(REGION) --project $(PROJECT_ID) --quiet

.PHONY: local build push deploy clean run init destroy
