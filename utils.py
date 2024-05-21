import os
from langchain_openai import AzureOpenAIEmbeddings
from langchain_openai import AzureChatOpenAI
import json
from pathlib import Path

class EnvironmentVariableNotSetError(Exception):
    pass

def validate_env_vars(*vars):
    for var in vars:
        if os.environ.get(var) is None or os.environ.get(var) == "":
            raise EnvironmentVariableNotSetError(f"Environment variable '{var}' is not set.")

def get_openai_clients() -> tuple[AzureChatOpenAI, AzureOpenAIEmbeddings]:
    required_vars = [
        "OPENAI_API_VERSION",
        "AZURE_OPENAI_DEPLOYMENT",
        "OPENAI_API_KEY",
        "AZURE_OPENAI_KEY",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME",
        "AZURE_OPENAI_ENDPOINT"
    ]
    
    validate_env_vars(*required_vars)

    azure_llm: AzureChatOpenAI = AzureChatOpenAI(
        temperature=0,
        openai_api_version=os.environ.get("OPENAI_API_VERSION"),
        azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT"),
        api_key=os.environ.get("AZURE_OPENAI_KEY")
    )
    azure_embeddings: AzureOpenAIEmbeddings = AzureOpenAIEmbeddings(
        azure_deployment=os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME"),
        openai_api_version=os.environ.get("OPENAI_API_VERSION"),
        azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
    )
    return azure_llm, azure_embeddings

def get_embedchain_settings(task_id: str) -> dict:
    required_vars = [
        "AZURE_OPENAI_LLM_DEPLOYMENT_NAME",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME",
    ]
    
    validate_env_vars(*required_vars)

    return {
        'llm': {
            'provider': 'azure_openai',
            'config': {
                'model': 'gpt-4', # TBD: set from env variable
                'deployment_name': os.environ.get("AZURE_OPENAI_LLM_DEPLOYMENT_NAME"),
                'temperature': 0.5,
                'max_tokens': 1000,
                'top_p': 1,
                'stream': False,
            },
        },
        'embedder': {
            'provider': 'azure_openai',
            'config': {
                'model': 'text-embedding-ada-002', # TBD: set from env variable
                'deployment_name': os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME"),
            },
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