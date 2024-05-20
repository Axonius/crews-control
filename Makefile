BUILD		= build
RUN			= run
RUN_IT		= run_it
CLEAN		= clean
TEST		= test
BENCHMARK	= benchmark

all: $(BUILD) $(RUN)

$(BUILD):
	mkdir -p db
	docker build . -t crews_control --build-arg CACHEBUSTER=$$(date +%s)

$(RUN_IT):
	make $(BUILD)
	mkdir -p $(PWD)/projects/$(project_name)/output
	docker run \
		-it \
		--env-file .env \
		-v $(PWD)/db:/app/db \
		-v $(PWD)/projects/$(project_name)/output:/app/projects/$(project_name)/output \
		crews_control \
		python main.py --project-name $(project_name)

$(RUN):
	make $(BUILD)
	mkdir -p $(PWD)/projects/$(project_name)/output
	docker run \
		--env-file .env \
		-v $(PWD)/db:/app/db \
		-v $(PWD)/projects/$(project_name)/output:/app/projects/$(project_name)/output \
		crews_control \
		# pass rest of the arguments as --params key1=value1 key2=value2 pairs
		python main.py --project-name $(project_name) --params $(PARAMS)

$(BENCHMARK):
	make $(BUILD)
	docker run \
		-it \
		--env-file .env \
		-v $(PWD)/db:/app/db \
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

.PHONY: all $(BUILD) $(RUN)