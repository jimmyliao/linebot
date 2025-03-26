# Makefile

PROJECT_ID := gde-kj
REGION := asia-east1
SERVICE_NAME := linebot
IMAGE_NAME := gcr.io/$(PROJECT_ID)/$(SERVICE_NAME)
NGROK_TOKEN := $(shell cat .env | grep NGROK_TOKEN | cut -d'=' -f2)
TARGET_PLATFORM := linux/amd64

# Local run
local:
	python app.py

# Local ACT to simulate GitHub Actions
local-act:
	act --container-architecture $(TARGET_PLATFORM) -j lint

# Build Docker image
build:
	docker buildx build --platform $(TARGET_PLATFORM) -t $(IMAGE_NAME) .

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

.PHONY: local build push deploy clean run
