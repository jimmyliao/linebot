# Makefile

PROJECT_ID := gde-kj
REGION := asia-east1
SERVICE_NAME := linebot
IMAGE_NAME := gcr.io/$(PROJECT_ID)/$(SERVICE_NAME)

# Local run
local:
	python app.py

# Build Docker image
build:
	docker build -t $(IMAGE_NAME) .

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

.PHONY: local build push deploy clean
