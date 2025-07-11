import hashlib
import os
import typing
from pathlib import Path
import time
import rich
from crewai import Task, Agent, Crew
from crewai.crews.crew_output import CrewOutput
from execution.contexts import load_crew_contexts
from execution.consts import EXIT_ON_ERROR
from execution.generic_validator import set_guardrail_llm, create_generic_task_validator_function
from tools.index import get_tool
from utils import is_safe_path
import re
import logging
from typing import Optional, Union

from execution.condition_evaluator import evaluate_condition_block

logger = logging.getLogger(__name__)

class NoAgentFoundError(Exception):
    pass

class NoTaskFoundError(Exception):
    pass

class CrewRunner:
    def __init__(
        self,
        project_name: str,
        crew_name: str,
        crew_config: dict,
        user_inputs: dict,
        previous_crews_results: dict,
        llm,
        embedding_model,
        should_export_results: bool = True,
        ignore_cache: bool = False,
        guardrail_verbose_logging: bool = False
    ):
        self._crew_name: str = crew_name
        self._user_input: dict = user_inputs
        self._crew_config: dict = crew_config
        self._project_name: str = project_name
        self._previous_results: dict = previous_crews_results # Contains {'status': '...', 'output': '...'}
        self._llm_clients: Dict[str, Any] = {'default': llm} # The 'llm' passed in is the default client, stored in a cache.
        self._embedding_model = embedding_model
        self._crew_context: typing.Optional[dict] = None
        self._ignore_cache: bool = ignore_cache

        set_guardrail_llm(self._llm, verbose_logging=guardrail_verbose_logging)

        # Store resolved_inputs definitions per task for later evaluation
        # _resolved_inputs_definitions_by_task will be like {task_name: {'resolved_input_name': {'case': [...], 'default': '...'}}}
        self._resolved_inputs_definitions_by_task: dict[str, Optional[dict]] = {
            task_name: task_config.get('resolved_inputs')
            for task_name, task_config in crew_config.get('tasks', {}).items()
        }

        # evaluate paths (for context files)
        for key, value in (crew_config.get('context') or {}).items():
            crew_config['context'][key] = self._evaluate_input_with_base_contexts(value)

        # load crew context
        self._crew_context: dict = load_crew_contexts(project_name, crew_config)

        # output file
        self._should_export_results: bool = should_export_results

        # validate crew parameters (agents/tasks presence)
        self.validate_crew_parameters()

    def _get_llm_client(self, model_config: Optional[dict] = None) -> Any:
        """
        Gets an LLM client based on a model configuration object from the YAML.
        If no config is provided, returns the default client. Caches clients for reuse.
        """
        if not model_config:
            return self._llm_clients['default']

        provider = model_config.get('provider')
        if not provider:
            rich.print(f"[bold red]Error: 'llm_model' config for an agent is missing the 'provider' key. Using default LLM.[/bold red]")
            return self._llm_clients['default']
            
        model_name = model_config.get('model_name')
        cache_key = f"{provider}-{model_name}" if model_name else provider

        if cache_key in self._llm_clients:
            rich.print(f"[blue]Using cached LLM client for: {cache_key}[/blue]")
            return self._llm_clients[cache_key]

        rich.print(f"[yellow]Initializing new LLM client for: {cache_key}...[/yellow]")
        try:
            llm_config_path = Path('config') / 'llms' / f'{provider}.json'
            if not llm_config_path.exists():
                raise FileNotFoundError(f"LLM config file not found for provider '{provider}' at {llm_config_path}")
            
            base_config = load_config(llm_config_path)
            
            # Call the factory with the base config and the specific overrides from the YAML
            new_client = create_llm_client(base_config, overrides=model_config)
            
            self._llm_clients[cache_key] = new_client
            return new_client

        except Exception as e:
            rich.print(f"[bold red]Error: Failed to create LLM client for '{cache_key}'. Using default LLM as fallback. Error: {e}[/bold red]")
            return self._llm_clients['default']

    def _check_output_condition(self, condition: dict, output_text: str) -> bool:
        """Evaluates if the output text meets all specified conditions."""
        checks = []
    
        if 'output_contains' in condition:
            expected = condition['output_contains']
            checks.append(expected.strip().upper() in output_text.strip().upper())
    
        if 'output_not_contains' in condition:
            forbidden = condition['output_not_contains']
            checks.append(forbidden.strip().upper() not in output_text.strip().upper())
    
        # All conditions must be satisfied (logical AND)
        return all(checks) if checks else True

    def _parse_and_get_tools(self, tools_config: list, tool_scope: typing.Optional[str] = None) -> list:
        """Parses the tool configuration from YAML and returns a list of instantiated tool objects."""
        if not tools_config:
            return []

        parsed_tools = []
        for tool_entry in tools_config:
            tool_params = {}
            if isinstance(tool_entry, str):
                tool_name = tool_entry
            elif isinstance(tool_entry, dict):
                # Make a copy so we can safely pop the name
                tool_config_copy = tool_entry.copy()
                tool_name = tool_config_copy.pop('name', None)
                if not tool_name:
                    raise ValueError(f"A tool configuration is missing its 'name' key: {tool_entry}")
                # The rest of the dict items are parameters for the tool's __init__
                tool_params = tool_config_copy
            else:
                raise TypeError(f"Invalid tool configuration format. Expected a string or a dictionary, but got {type(tool_entry)}.")

            # Call the updated get_tool function with the unpacked parameters
            tool_object = get_tool(
                tool_name,
                task_id=self._get_tool_id(tool_scope),
                **tool_params
            )
            parsed_tools.append(tool_object)
        
        return parsed_tools

    def validate_crew_parameters(self):
        """Validate internal parameters that crew needs from 3rd parties."""
        # validations
        if 'agents' not in self._crew_config:
            raise NoAgentFoundError('Crew config must have at least one agent.')
        if 'tasks' not in self._crew_config:
            raise NoTaskFoundError('Crew config must have at least one task.')
        # check no intersection between _crew_context and _user_input
        if set(self._crew_context.keys()) & set(self._user_input.keys()) & set(self._previous_results.keys()):
            raise ValueError('Crew context and user input must not have any intersection.')

    def _get_base_formatting_context(self) -> dict:
        """
        Compiles the base dictionary for string formatting, containing:
        - Crew-level context (from files)
        - User-provided inputs
        - Raw string outputs from previous crews
        """
        previous_outputs_only = {
            crew_name: result.get('output', '')
            for crew_name, result in (self._previous_results or {}).items()
        }
        
        # Merge contexts, user inputs, and previous crew outputs
        # User inputs might override context, previous outputs might override user inputs
        # But this only impacts direct string formatting; resolved_inputs evaluate previous_results directly.
        combined_context = {}
        combined_context.update(self._crew_context or {})
        combined_context.update(self._user_input or {})
        combined_context.update(previous_outputs_only) # This ensures crew outputs are available as {crew_name}
        
        return combined_context

    def _evaluate_input_with_base_contexts(self, input_template: str) -> str:
        """
        Evaluates a template string using only the base contexts (crew_context, user_input, previous_crew_outputs).
        Used for things like context file paths or simple parameters.
        """
        base_context = self._get_base_formatting_context()
        try:
            return input_template.format(**base_context)
        except (ValueError, KeyError) as e: # Catch KeyError too, for missing placeholders in base contexts
            raise ValueError(f'\nError evaluating base input: {e}\nInput template:\n---\n{input_template}\n---\n')


    def _resolve_dynamic_input(self, input_name: str, task_name: str, base_formatting_context: dict) -> str:
        """
        Resolves a single dynamic input defined in the 'resolved_inputs' section for a specific task.
        """
        task_resolved_inputs_config = self._resolved_inputs_definitions_by_task.get(task_name)
        
        if not task_resolved_inputs_config:
            # No resolved_inputs defined for this task, or for this specific input_name.
            # This should ideally not be called if not defined, but as a safeguard.
            return "" # Or raise an error if dynamic input is expected but not configured

        dynamic_input_definition = task_resolved_inputs_config.get(input_name)

        if not dynamic_input_definition:
            # The specific dynamic input 'input_name' is not defined for this task.
            return "" # Or raise an error if dynamic input is expected but not configured

        # Iterate through cases in order
        for case in dynamic_input_definition.get('case', []):
            condition_block = case.get('condition')
            
            # Evaluate the condition using the reusable function
            if evaluate_condition_block(condition_block, self._previous_results):
                # Condition met, resolve the value. This value itself might contain placeholders.
                raw_value_template = case.get('value', '')
                try:
                    return raw_value_template.format(**base_formatting_context)
                except (ValueError, KeyError) as e:
                    raise ValueError(f"Error resolving dynamic input '{input_name}' for task '{task_name}': Missing key in context for value template: {e}. Template: '{raw_value_template}'")
        
        # If no case matched, check for a default value
        if 'default' in dynamic_input_definition:
            default_value_template = dynamic_input_definition['default']
            try:
                return default_value_template.format(**base_formatting_context)
            except (ValueError, KeyError) as e:
                    raise ValueError(f"Error resolving dynamic input '{input_name}' for task '{task_name}': Missing key in context for default template: {e}. Template: '{default_value_template}'")

        # If no case matched and no default is provided
        return "" # Or raise an error, depending on desired strictness for missing default.


    def _evaluate_input(self, user_input_template: str, task_name: Optional[str] = None) -> str:
        """
        Evaluates a template string using crew context, user inputs, previous crew outputs,
        and dynamically resolved inputs for a specific task.
        """
        # First, gather all base contexts
        base_context = self._get_base_formatting_context()
        
        # Then, if a task_name is provided and it has resolved_inputs, resolve them
        resolved_dynamic_inputs_for_task = {}
        if task_name and self._resolved_inputs_definitions_by_task.get(task_name):
            for dynamic_input_name in self._resolved_inputs_definitions_by_task[task_name].keys():
                resolved_value = self._resolve_dynamic_input(dynamic_input_name, task_name, base_context)
                resolved_dynamic_inputs_for_task[dynamic_input_name] = resolved_value
        
        # Combine all available contexts for the final formatting pass
        final_formatting_context = {}
        final_formatting_context.update(base_context)
        final_formatting_context.update(resolved_dynamic_inputs_for_task) # Dynamic inputs override if names clash (unlikely)

        try:
            # Handle SHA-256 stripping first for any input templates
            templated_input_after_sha_strip = self._strip_sha256(user_input_template)
            return templated_input_after_sha_strip.format(**final_formatting_context)
        except (ValueError, KeyError) as e: # Catch both ValueError from format() and KeyError for missing placeholders
            raise ValueError(f'\nError evaluating input: Missing expected placeholder: {e}\nUser input:\n---\n{user_input_template}\n---\n')


    def _strip_sha256(self, user_input: str) -> str:
        sha256_pattern = re.compile(r'\{sha256:(\w+)\}')
        return sha256_pattern.sub(r'{\1}', user_input)

    def _replace_sha256(self, user_input: str) -> str:
        # Define a regex pattern to find {sha256:(\w+)}
        sha256_pattern = re.compile(r'\{sha256:(\w+)\}')
        
        def replace_match(match):
            var_name = match.group(1)
            # Get the variable value from the context
            # For SHA-256, we need raw value, not just formatted string.
            # This logic needs to pull directly from the original sources.
            var_value = (self._crew_context or {}).get(var_name) or \
                        (self._user_input or {}).get(var_name) or \
                        (self._previous_results or {}).get(var_name, {}).get('output') # Access 'output' from previous_results dict
            if var_value is None:
                raise ValueError(f"Variable '{var_name}' not found in context for SHA-256 hashing.")
            
            # If var_value is a CrewOutput object (from before the orchestrator fix), get its raw.
            if isinstance(var_value, CrewOutput):
                var_value = var_value.raw

            # Compute SHA-256 hash
            hash_object = hashlib.sha256(var_value.encode())
            return hash_object.hexdigest()
        
        # Replace {sha256:<variable>} patterns with their SHA-256 hash
        return sha256_pattern.sub(replace_match, user_input)

    def _evaluate_for_output_file(self, user_input: str) -> str:
        # First, handle SHA-256 replacements
        # For output file naming, we only use base contexts for SHA-256 and formatting
        base_context = self._get_base_formatting_context()
        templated_input_after_sha_strip = self._strip_sha256(user_input)
        
        # Perform SHA-256 replacements based on base contexts (crew_context, user_input, prev_outputs)
        input_after_sha_hash = self._replace_sha256(templated_input_after_sha_strip)
        
        # Then, perform regular formatting with all base contexts
        try:
            return input_after_sha_hash.format(**base_context)
        except ValueError as e:
            raise ValueError(f'\nError evaluating output file name: {e}\nInput template:\n---\n{user_input}\n---\n')
        except KeyError as e:
            raise ValueError(f'\nError evaluating output file name: Missing expected placeholder: {e}\nInput template:\n---\n{user_input}\n---\n')


    @property
    def _output_file(self) -> str:
        # Automatically evaluate when accessing the _output_file property
        # Note: _output_file evaluation does NOT include resolved_inputs as they are task-specific
        return self._evaluate_for_output_file(self._crew_config.get('output_naming_template') or '').replace('/', '-')

    def _get_tool_id(self, scope: typing.Optional[str] = None) -> str:
        if scope is None:
            return hashlib.md5(f'{self._crew_name}{list(self._user_input.values())}'.lower().encode()).hexdigest()
        return hashlib.md5(f'{self._crew_name}{scope}{list(self._user_input.values())}'.lower().encode()).hexdigest()

    def _get_agent(self, agent_name: str, agent_scope: typing.Optional[str] = None) -> Agent:
        agent_config: dict = self._crew_config['agents'].get(agent_name)
        try:
            # Parse the tools configuration from the YAML
            agent_tools = self._parse_and_get_tools(
                tools_config=agent_config.get('tools') or [],
                tool_scope=agent_scope
            )

            agent_llm_config = agent_config.get('llm_model') # Get the specific LLM configuration object for this agent
            agent_llm_client = self._get_llm_client(agent_llm_config) # and fetch the corresponding LLM client

            # Agent role, goal, backstory are evaluated here.
            # These should use the *full* context including resolved inputs if they are configured for agents.
            # Assuming agent_scope implies task_name for resolved_inputs
            return Agent(
                role=self._evaluate_input(agent_config['role'], task_name=agent_scope),
                goal=self._evaluate_input(agent_config['goal'], task_name=agent_scope),
                tools=agent_tools,
                backstory=self._evaluate_input(agent_config['backstory'], task_name=agent_scope),
                allow_delegation=False,
                llm=agent_llm_client,
                embedding_model=self._embedding_model,
                verbose=True,
                memory=True,
                multimodal=True,
            )
        except ValueError as e:
            raise ValueError(f'Error evaluating agent: {agent_name}. Error: {e}')

    def _get_crew_tasks(self) -> list[Task]:
        tasks_config = self._crew_config.get('tasks', {})
        task_objects = {}

        # First pass: Create all task objects without their context.
        for task_name, task_config in tasks_config.items():
            guardrail_function = None
            guardrail_type = task_config.get('guardrail_type')

            evaluated_description = self._evaluate_input(task_config['description'], task_name=task_name)
            evaluated_expected_output = self._evaluate_input(task_config['expected_output'], task_name=task_name)
            raw_expected_output_template_for_validator = task_config['expected_output']

            if guardrail_type == "generic_agent_validator":
                guardrail_function = create_generic_task_validator_function(
                    main_task_description_str=evaluated_description,
                    main_task_expected_output_str=raw_expected_output_template_for_validator
                )
                logger.info(f"Generic agent-based guardrail enabled for task: {task_name}")

            # FIX: Use the helper method to correctly parse the tools list for the task.
            task_tools = self._parse_and_get_tools(
                tools_config=task_config.get('tools', []),
                tool_scope=task_name
            )

            task_instance = Task(
                description=evaluated_description,
                expected_output=evaluated_expected_output,
                agent=self._get_agent(agent_name=task_config['agent'], agent_scope=task_name),
                tools=task_tools, # Use the correctly parsed list of tool objects
                guardrail=guardrail_function,
            )
            task_objects[task_name] = task_instance

        # Second pass: Link contexts now that all task objects exist.
        for task_name, task_config in tasks_config.items():
            if 'context' in task_config:
                context_task_names = task_config['context']
                context_task_objects = [task_objects[name] for name in context_task_names if name in task_objects]
                if context_task_objects:
                    task_objects[task_name].context = context_task_objects
        
        # The final list of tasks must be in the order they appear in the YAML
        # to ensure correct execution sequence for crews with parallel tasks.
        ordered_tasks = [task_objects[name] for name in tasks_config.keys()]
        return ordered_tasks
    
    def _generate_agents(self) -> list[Agent]:
        return [
            self._get_agent(agent_name)
            for agent_name, agent_config in list(self._crew_config.get('agents').items()) or []
        ]

    def _export_results(self, results: CrewOutput):
        if self._should_export_results:
            export_path: Path = self._get_export_path()
            rich.print(
                f'[green bold]'
                f'Writing {self._crew_name} result into <{export_path}>'
                f'[/green bold]'
            )
            if not export_path.parent.exists():
                export_path.parent.mkdir(parents=True, exist_ok=True)
            export_path.write_text(results.raw)
        else:
            rich.print(f"[green bold]Crew <{self._crew_name}> result:\n{results}\n\n[/green bold]")

    def _get_export_path(self) -> Path:
        if not is_safe_path(Path.cwd() / 'projects' / self._project_name / 'output',
                            Path.cwd() / 'projects' / self._project_name / 'output' / self._output_file):
            rich.print(f"[red bold]Error: Directory traversal detected in output file {self._output_file}[/red bold]")
            os._exit(1)
        return Path.cwd() / 'projects' / self._project_name / 'output' / self._output_file

    def run_crew(self) -> str:
        run_until_config = self._crew_config.get('run_until')
        if not run_until_config:
            export_path: Path = self._get_export_path()
            if not self._ignore_cache and export_path.exists():
                cached_content = export_path.read_text()
                rich.print(f"[yellow bold]Using cached result for <{self._crew_name}>[/yellow bold]")
                return cached_content # Return the plain string directly from cache
            return self._execute_crew_with_error_handling()

        max_retries = run_until_config.get('max_retries', 3)        
        if max_retries == 0:
            raise ValueError("max_retries=0 is invalid. To run once, remove the 'run_until' block entirely.")
        if max_retries < -1:
            raise ValueError("max_retries must be -1 for infinite retries or a positive integer (>= 1) for limited retries.")

        delay = run_until_config.get('delay_seconds', 0)
        condition = run_until_config.get('condition', {})
        rich.print(f"[cyan bold]Crew <{self._crew_name}> will run until condition is met (max {max_retries} retries).[/cyan bold]")

        attempt = 0
        final_result_raw = ""
        
        while max_retries == -1 or attempt < max_retries:
            attempt += 1
            rich.print(f"[cyan]Attempt {attempt}/{max_retries} for crew <{self._crew_name}>...[/cyan]")
            self._ignore_cache = True # Force cache to be ignored during looping
            result_raw = self._execute_crew_with_error_handling()
            final_result_raw = result_raw # Always store the latest result
            if self._check_output_condition(condition, result_raw):
                rich.print(f"[green bold]Condition met for <{self._crew_name}>. Proceeding.[/green bold]")
                break # Exit the loop on success

            rich.print(f"[yellow]Condition not met for <{self._crew_name}>.[/yellow]")
            if attempt < max_retries:
                if delay > 0:
                    rich.print(f"[yellow]Waiting {delay} seconds before next attempt...[/yellow]")
                    time.sleep(delay)
            else:
                rich.print(f"[red bold]Max retries reached for <{self._crew_name}>. Using the last result.[/red bold]")

        final_output_obj = CrewOutput(raw=final_result_raw, pydantic_output=None, tasks_output=[])
        self._export_results(final_output_obj)
        
        return final_result_raw

    def _execute_crew_with_error_handling(self) -> str:
        """Encapsulates the core crew execution and transient error retries."""
        max_retries = 5
        retry_count = 0
        backoff_factor = 2

        while retry_count < max_retries:
            try:
                results: CrewOutput = Crew(
                    agents=self._generate_agents(),
                    tasks=self._get_crew_tasks(),
                    verbose=True
                ).kickoff()
                
                # In the looping case, the final export is handled outside this method.
                # In the single-run case, this export is the one that runs.
                if not self._crew_config.get('run_until'):
                    self._export_results(results)

                return results.raw
            except Exception as e:
                error_code = self._extract_error_code(e)
                rich.print(f"[red bold]Error occurred while running crew <{self._crew_name}>[/red bold]")
                rich.print(f"[red bold]Exception details: {e}[/bold red]")
                if error_code == "429":
                    retry_count += 1
                    wait_time = backoff_factor ** retry_count
                    rich.print(f"[yellow bold]Rate limit error encountered. Retrying in {wait_time} seconds...[/yellow bold]")
                    time.sleep(wait_time)
                else:
                    if EXIT_ON_ERROR:
                        os._exit(1)
                    return str(e)

        rich.print(f"[red bold]Exceeded maximum retries for transient errors. Aborting...[/bold red]")
        return "Rate limit error: Exceeded maximum retries"

    def _extract_error_code(self, exception: Exception) -> str:
        if hasattr(exception, 'response') and hasattr(exception.response, 'status_code'):
            return str(exception.response.status_code)
        return ""
