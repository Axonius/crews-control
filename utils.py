import os
from langchain_openai import AzureOpenAIEmbeddings
from langchain_openai import AzureChatOpenAI
from langchain_groq import ChatGroq
from langchain_community.embeddings import GPT4AllEmbeddings
import json
from pathlib import Path
import re
from langchain_community.embeddings import HuggingFaceEmbeddings

class EnvironmentVariableNotSetError(Exception):
    pass


def sanitize_filename(filename: str) -> str:
    """Sanitize the filename by replacing non-alphanumeric characters with underscores."""
    return re.sub(r'[^a-zA-Z0-9]', '_', filename).lower()

def is_safe_path(base_dir: Path, path: Path) -> bool:
    """Check if the resolved path is within the base directory to prevent path traversal."""
    try:
        return path.resolve().is_relative_to(base_dir.resolve())
    except ValueError:
        return False

def validate_env_vars(*vars):
    # Handle single list or tuple containing a list
    if len(vars) == 1 and isinstance(vars[0], list):
        vars = vars[0]

    for var in vars:
        if os.getenv(var) is None or os.getenv(var) == "":
            raise EnvironmentVariableNotSetError(f"Environment variable '{var}' is not set.")

def create_llm_client(config):
    provider = config['provider']
    validate_env_vars(config['required_vars'])
    
    if provider == 'groq':
        return ChatGroq(
            model=os.getenv("GROQ_MODEL_NAME"),
            api_key=os.getenv("GROQ_API_KEY"),
            streaming=config.get('stream', True),
            max_tokens=config.get('max_tokens', 8192),
            model_name=os.getenv('GROQ_MODEL_NAME'),
        )
    elif provider == 'azure_openai':
        return AzureChatOpenAI(
            temperature=config.get('temperature', 0),
            openai_api_version=os.getenv("OPENAI_API_VERSION"),
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            api_key=os.environ["AZURE_OPENAI_KEY"],
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        )
    # Add more LLM providers here as needed
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

def create_embedder_client(config):
    provider = config['provider']
    
    if provider == 'gpt4all':
        return GPT4AllEmbeddings(provider="gpt4all")
    elif provider == 'azure_openai':
        validate_env_vars(config['required_vars'])
        return AzureOpenAIEmbeddings(
            azure_deployment=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME"],
            openai_api_version=os.environ["OPENAI_API_VERSION"],
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
    elif provider == 'huggingface':
        return HuggingFaceEmbeddings(
            model_name=config['config']['model'],
        )

    # Add more embedder providers here as needed
    else:
        raise ValueError(f"Unsupported embedder provider: {provider}")

def get_clients(llm_name: str, embedder_name: str):
    llm_config_path = Path('config') / 'llms' / f'{llm_name}.json'
    embedder_config_path = Path('config') / 'embedders' / f'{embedder_name}.json'
    
    llm_config = load_config(llm_config_path)
    embedder_config = load_config(embedder_config_path)
    
    llm_client = create_llm_client(llm_config)
    embedder_client = create_embedder_client(embedder_config)
    
    return llm_client, embedder_client

def load_config(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

def get_embedchain_settings(task_id: str, llm_name: str, embedder_name: str) -> dict:
    llm_config_path = Path('config') / 'llms' / f'{llm_name}.json'
    embedder_config_path = Path('config') / 'embedders' / f'{embedder_name}.json'
    
    llm_config = load_config(llm_config_path)
    embedder_config = load_config(embedder_config_path)

    if llm_name == 'azure_openai':
        llm, embedder = get_clients(llm_name=llm_name, embedder_name=embedder_name)
        llm_config['config']['deployment_name'] = getattr(llm, 'deployment_name')
        llm_config['config']['api_key'] = getattr(llm, 'openai_api_key')
        embedder_config['config']['deployment_name'] = getattr(embedder, 'deployment')
        embedder_config['config']['api_key'] = getattr(embedder, 'openai_api_key')

    return {
        'llm': {
            'provider': llm_config['provider'],
            'config': llm_config['config'],
        },
        'embedder': {
            'provider': embedder_config['provider'],
            'config': embedder_config['config'],
        },
        'app': {
            'config': {
                'id': task_id,
                'collect_metrics': False,
            },
        },
    }


def get_validated_input(prompt: str, valid_options: list[str] = None) -> str:
    while True:
        user_input = input(prompt).strip()
        if not user_input:
            print("Input cannot be empty.")
        elif valid_options is not None and user_input not in valid_options:
            print(f"Please enter a valid option from {valid_options}")
        else:
            return user_input

def report_success_percentage(folder_path):
    total_files = 0
    success_files = 0
    failed_details = []

    # Iterate through all files in the given directory
    for filename in os.listdir(folder_path):
        if filename.endswith(".result"):
            total_files += 1
            path: Path = Path.cwd() / folder_path / filename
            with open(path, 'r') as file:
                try:
                    data = json.load(file)
                except json.JSONDecodeError:
                    print(f"Error reading file {filename}")
                    failed_details.append((filename, ["Error reading file"]))
                    continue

                # Check each metric in the file
                has_failure = False
                file_failures = []
                for metric, verdict in data.items():
                    if not verdict.get("res", False):  # Check if the result is False or absent
                        has_failure = True
                        reason = verdict.get("reason", "No reason provided")
                        file_failures.append(f"{metric}: {reason}")

                if has_failure:
                    failed_details.append((filename, file_failures))
                else:
                    success_files += 1

    # Calculate success percentage
    if total_files > 0:
        success_percentage = (success_files / total_files) * 100
    else:
        success_percentage = 100  # Default to 100% if no .result files are found

    print(f"Success percentage: {success_percentage:.2f}%")
    if failed_details:
        print("Failed files and reasons:")
        for filename, failures in failed_details:
            print(f"{filename}:")
            for failure in failures:
                print(f"  {failure}")
    else:
        print("All files succeeded!")

def list_models():
    def list_model_files(directory, model_type):
        print("-" * 30)
        print(f"Available {model_type} models:")
        print("-" * 30)
        path = Path('config') / directory
        if not path.exists():
            print(f"The directory {path} does not exist.")
            return

        for file in path.glob('*.json'):
            print(f'- {file.stem}')
        print()

    list_model_files('llms', 'LLM')
    list_model_files('embedders', 'Embedder')

def list_tools():
    print("-" * 30)
    print("Available tools:")
    print("-" * 30)
    from tools.index import _TOOLS_MAP
    for tool_name in _TOOLS_MAP.keys():
        print(f'- {tool_name}')

def list_projects():
    print("-" * 30)
    print("Available projects:")
    print("-" * 30)
    path = Path('projects')
    if not path.exists():
        print(f"The directory {path} does not exist.")
        return

    for project in path.iterdir():
        if project.is_dir():
            print(f'- {project.name}')
    print()