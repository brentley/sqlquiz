.PHONY: help dev test build deploy logs shell stop clean init-db

help:
	@echo "Available commands:"
	@echo "  make dev        - Start development environment"
	@echo "  make test       - Run tests"
	@echo "  make build      - Build Docker image"
	@echo "  make deploy     - Deploy to production (automated via GitHub Actions)"
	@echo "  make logs       - View logs"
	@echo "  make shell      - Access container shell"
	@echo "  make stop       - Stop all containers"
	@echo "  make clean      - Clean up everything"
	@echo "  make init-db    - Initialize database with sample data"

dev:
	@echo "Starting SQLQuiz development environment..."
	docker compose -f docker-compose.dev.yml up --build

test:
	@echo "Running SQLQuiz test suite..."
	docker compose -f docker-compose.test.yml up --build --abort-on-container-exit

build:
	@echo "Building SQLQuiz Docker image..."
	docker compose build

deploy:
	@echo "Deployment is automated via GitHub Actions"
	@echo "Push to main branch to trigger deployment"
	@echo "Manual deployment:"
	@echo "  1. Ensure you're on the production server"
	@echo "  2. Pull latest changes: git pull origin main"
	@echo "  3. Run: docker compose up -d"

logs:
	@echo "Viewing SQLQuiz logs..."
	docker compose logs -f

shell:
	@echo "Accessing SQLQuiz container shell..."
	docker compose exec sqlquiz /bin/bash

shell-dev:
	@echo "Accessing development container shell..."
	docker compose -f docker-compose.dev.yml exec sqlquiz-dev /bin/bash

stop:
	@echo "Stopping all SQLQuiz containers..."
	docker compose down

stop-dev:
	@echo "Stopping development containers..."
	docker compose -f docker-compose.dev.yml down

clean:
	@echo "Cleaning up SQLQuiz environment..."
	docker compose down -v
	docker system prune -f

init-db:
	@echo "Initializing database with healthcare data..."
	@if [ ! -f healthcare_quiz.db ]; then \
		echo "Creating database..."; \
		python3 load_data.py; \
		echo "Database initialized successfully!"; \
	else \
		echo "Database already exists. Delete healthcare_quiz.db to recreate."; \
	fi

# Development helpers
dev-setup:
	@echo "Setting up development environment..."
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt
	make init-db
	@echo "Development setup complete!"
	@echo "Activate virtual environment: source .venv/bin/activate"
	@echo "Start development server: python3 app.py"

# Production helpers
prod-logs:
	@echo "Viewing production logs on server..."
	ssh ec2-user@18.118.142.110 "cd sqlquiz && docker compose logs -f"

prod-status:
	@echo "Checking production status..."
	ssh ec2-user@18.118.142.110 "cd sqlquiz && docker compose ps"

prod-health:
	@echo "Checking production health..."
	curl -s https://sqlquiz.visiquate.com/health | jq .

# Security
security-scan:
	@echo "Running security scans..."
	bandit -r . -f json -o bandit-report.json || true
	safety check --json || true
	pip-audit --format=json || true
	@echo "Security scan complete. Check reports for issues."