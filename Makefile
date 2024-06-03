.DEFAULT_GOAL := $(HELP)

BUILD					= build
RUN						= run
RUN_IT					= run-it
BENCHMARK				= benchmark
CLEAN					= clean
COMPILE_REQUIREMENTS	= compile-requirements
DEV						= dev
LIST_TOOLS				= list-tools
LIST_MODELS				= list-models
LIST_PROJECTS			= list-projects
CLEANUP					= cleanup
HELP					= help

help:
	@echo "Usage:"
	@echo "  make $(RUN_IT) PROJECT_NAME=<your_project_name>"
	@echo "  make $(RUN) PROJECT_NAME=<your_project_name> PARAMS=\"<key1=value1 key2=value2>\""
	@echo "  make $(BENCHMARK) PROJECT_NAME=<your_project_name>"
	@echo "  make $(BUILD)"
	@echo "  make $(CLEAN)"
	@echo "  make $(COMPILE_REQUIREMENTS)"
	@echo "  make $(DEV)"
	@echo "  make $(LIST_TOOLS)"
	@echo "  make $(LIST_MODELS)"
	@echo "  make $(LIST_PROJECTS)"
	@echo "  make $(CLEANUP)"
	@echo "  make $(HELP)"
	@echo
	@echo "Available targets:"
	@echo "  $(RUN_IT)               - Runs a project in Interactive mode (requires PROJECT_NAME)"
	@echo "  $(RUN)                  - Runs a project in CLI mode (requires PROJECT_NAME and PARAMS)"
	@echo "  $(BENCHMARK)            - Run a project in benchmark mode (requires PROJECT_NAME)"
	@echo "  $(BUILD)                - Build the Docker image"
	@echo "  $(CLEAN)                - Clean up generated files"
	@echo "  $(COMPILE_REQUIREMENTS) - Recompile the requirements files"
	@echo "  $(DEV)                  - Install development requirements and generate LICENSES.md"
	@echo "  $(LIST_TOOLS)           - List available tools"
	@echo "  $(LIST_MODELS)          - List available LLM and Embedder models"
	@echo "  $(LIST_PROJECTS)        - List available projects"
	@echo "  $(CLEANUP)              - Perform Docker cleanup"
	@echo "  $(HELP)                 - Show this help message"
	@echo
	@echo "For license details, see the LICENSE file."


it: $(COMPILE_REQUIREMENTS) $(BUILD) $(RUN_IT)

$(CLEANUP):
	@docker container prune
	@docker image prune
	@docker builder prune

$(LIST_TOOLS):
	@docker run \
		-it \
		--env-file .env \
		-v $(PWD)/config:/app/config \
		-v $(PWD)/db:/app/db \
		-v $(PWD)/tools:/app/tools \
		-v $(PWD)/projects/$(PROJECT_NAME):/app/projects/$(PROJECT_NAME) \
		-v $(PWD)/projects/$(PROJECT_NAME)/output:/app/projects/$(PROJECT_NAME)/output \
		crews_control --list-tools

$(LIST_MODELS):
	@docker run \
		-it \
		--env-file .env \
		-v $(PWD)/config:/app/config \
		-v $(PWD)/db:/app/db \
		-v $(PWD)/tools:/app/tools \
		-v $(PWD)/projects/$(PROJECT_NAME):/app/projects/$(PROJECT_NAME) \
		-v $(PWD)/projects/$(PROJECT_NAME)/output:/app/projects/$(PROJECT_NAME)/output \
		crews_control --list-models

$(LIST_PROJECTS):
	@docker run \
		-it \
		--env-file .env \
		-v $(PWD)/config:/app/config \
		-v $(PWD)/db:/app/db \
		-v $(PWD)/tools:/app/tools \
		-v $(PWD)/projects/$(PROJECT_NAME):/app/projects/$(PROJECT_NAME) \
		-v $(PWD)/projects/$(PROJECT_NAME)/output:/app/projects/$(PROJECT_NAME)/output \
		crews_control --list-projects

$(DEV):
	@pip install -r requirements-dev.txt
	@pip-licenses -a -f markdown --output LICENSES.md

$(COMPILE_REQUIREMENTS):
	@pip install pip-tools
	@pip-compile --generate-hashes requirements-dev.in
	@pip-compile --generate-hashes requirements.in

$(BUILD):
	@mkdir -p db
	@pip install --upgrade pip
	@pip install --upgrade setuptools
	@docker build . -t crews_control --build-arg CACHEBUSTER=$$(date +%s)

$(RUN_IT):
	@if [ -z "$(PROJECT_NAME)" ]; then \
		echo "Error: PROJECT_NAME is not set."; \
		echo "Usage:"; \
		echo "  make $(RUN_IT) PROJECT_NAME=<your_project_name>"; \
		echo "or"; \
		echo "  export PROJECT_NAME=<your_project_name>"; \
		echo "  make $(RUN_IT)"; \
		exit 1; \
	fi

	@mkdir -p $(PWD)/projects/$(PROJECT_NAME)/output
	@docker run \
		-it \
		--env-file .env \
		-v $(PWD)/config:/app/config \
		-v $(PWD)/db:/app/db \
		-v $(PWD)/tools:/app/tools \
		-v $(PWD)/projects/$(PROJECT_NAME):/app/projects/$(PROJECT_NAME) \
		-v $(PWD)/projects/$(PROJECT_NAME)/output:/app/projects/$(PROJECT_NAME)/output \
		crews_control \
		--project-name $(PROJECT_NAME)

$(RUN):
	@if [ -z "$(PROJECT_NAME)" ]; then \
		echo "Error: PROJECT_NAME is not set."; \
		echo "Usage:"; \
		echo "  make $(RUN) PROJECT_NAME=<your_project_name> PARAMS=\"<key1=value1 key2=value2>\""; \
		echo "or"; \
		echo "  export PROJECT_NAME=<your_project_name>"; \
		echo "  export PARAMS=\"<key1=value1 key2=value2>\""; \
		echo "  make $(RUN)"; \
		exit 1; \
	fi
	@if [ -z "$(PARAMS)" ]; then \
		echo "Error: PARAMS is not set."; \
		echo "Usage:"; \
		echo "  make $(RUN) PROJECT_NAME=<your_project_name> PARAMS=\"<key1=value1 key2=value2>\""; \
		echo "or"; \
		echo "  export PROJECT_NAME=<your_project_name>"; \
		echo "  export PARAMS=\"<key1=value1 key2=value2>\""; \
		echo "  make $(RUN)"; \
		exit 1; \
	fi

	@mkdir -p $(PWD)/projects/$(PROJECT_NAME)/output
	@docker run \
		--env-file .env \
		-v $(PWD)/config:/app/config \
		-v $(PWD)/db:/app/db \
		-v $(PWD)/tools:/app/tools \
		-v $(PWD)/projects/$(PROJECT_NAME):/app/projects/$(PROJECT_NAME) \
		-v $(PWD)/projects/$(PROJECT_NAME)/output:/app/projects/$(PROJECT_NAME)/output \
		crews_control \
		--project-name $(PROJECT_NAME) --params $(PARAMS)

$(BENCHMARK):
	@docker run \
		-it \
		--env-file .env \
		-v $(PWD)/config:/app/config \
		-v $(PWD)/db:/app/db \
		-v $(PWD)/projects/$(PROJECT_NAME):/app/projects/$(PROJECT_NAME) \
		-v $(PWD)/projects/$(PROJECT_NAME)/output:/app/projects/$(project_name)/output \
		-v $(PWD)/projects/$(PROJECT_NAME)/validations:/app/projects/$(PROJECT_NAME)/validations \
		crews_control \
		--benchmark $(IGNORE_CACHE) --project-name $(PROJECT_NAME)

$(CLEAN):
	@rm -rf output
	@rm -rf db

.PHONY: it $(CLEANUP) $(DEV) $(LIST_TOOLS) $(LIST_MODELS) $(LIST_PROJECTS) $(BUILD) $(RUN) $(RUN_IT) $(CLEAN) $(BENCHMARK) $(COMPILE_REQUIREMENTS)
