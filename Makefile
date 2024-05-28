BUILD					= build
RUN						= run
RUN_IT					= run_it
CLEAN					= clean
TEST					= test
BENCHMARK				= benchmark
COMPILE_REQUIREMENTS	= compile-requirements
DEV						= dev

it: $(COMPILE_REQUIREMENTS) $(BUILD) $(RUN_IT)

$(DEV):
	pip install -r requirements-dev.txt
	pip-licenses -a -f markdown --output LICENSES.md

$(COMPILE_REQUIREMENTS):
	pip install pip-tools
	pip-compile --generate-hashes requirements-dev.in
	pip-compile --generate-hashes requirements.in

$(BUILD):
	mkdir -p db
	docker build . -t crews_control --build-arg CACHEBUSTER=$$(date +%s)

$(RUN_IT):
	mkdir -p $(PWD)/projects/$(project_name)/output
	docker run \
		-it \
		--env-file .env \
		-v $(PWD)/db:/app/db \
		-v $(PWD)/projects/$(project_name):/app/projects/$(project_name) \
		-v $(PWD)/projects/$(project_name)/output:/app/projects/$(project_name)/output \
		crews_control \
		python main.py --project-name $(project_name)

$(RUN):
	mkdir -p $(PWD)/projects/$(project_name)/output
	docker run \
		--env-file .env \
		-v $(PWD)/db:/app/db \
		-v $(PWD)/projects/$(project_name):/app/projects/$(project_name) \
		-v $(PWD)/projects/$(project_name)/output:/app/projects/$(project_name)/output \
		crews_control \
		# pass rest of the arguments as --params key1=value1 key2=value2 pairs
		python main.py --project-name $(project_name) --params $(PARAMS)

$(BENCHMARK):
	docker run \
		-it \
		--env-file .env \
		-v $(PWD)/db:/app/db \
		-v $(PWD)/projects/$(project_name):/app/projects/$(project_name) \
		-v $(PWD)/projects/$(project_name)/output:/app/projects/$(project_name)/output \
		-v $(PWD)/projects/$(project_name)/validations:/app/projects/$(project_name)/validations \
		crews_control \
		python main.py --benchmark $(IGNORE_CACHE) --project-name $(project_name)

$(CLEAN):
	rm -rf output
	rm -rf db

$(TEST):
	make $(BUILD)
	docker run -it --env-file .env -v $(PWD)/db:/app/db crews_control pytest execution/tests/ -vvv

.PHONY: it $(DEBV) $(BUILD) $(RUN) $(RUN_IT) $(CLEAN) $(TEST) $(BENCHMARK) $(COMPILE_REQUIREMENTS)
