# Crews Control

## Acknowledgements

This project builds upon the following MIT-licensed project:

- crewAI: https://github.com/joaomdmoura/crewAI by João Moura | crewAI™, Inc.: https://github.com/joaomdmoura/
  

**Crews Control** is an abstraction layer on top of [crewAI](https://www.crewai.com/), designed to facilitate the creation and execution of AI-driven projects without writing code. By defining an `execution.yaml` file, users can orchestrate AI crews to accomplish complex tasks using predefined or custom tools.

## Features

  - **No-Code AI Orchestration:** Define projects with `execution.yaml`, specifying crews, agents, and tasks.
  - **Advanced Conditional Logic:** Orchestrate complex workflows with `and`/`or` dependencies based on crew status (`SUCCESS`, `SKIPPED`) or output content (`output_contains`, `output_not_contains`).
  - **Dynamic Task Inputs:** Define task inputs (`description`, `expected_output`, etc.) dynamically at runtime based on the outcomes of previous crews using a `resolved_inputs` block.
  - **Modular Tools:** Use a set of predefined tools or create custom ones.
  - **Artifact Generation:** Each crew outputs a file artifact from the final task.
  - **Templated Outputs:** Access outputs from previous crews’ tasks using a powerful templating syntax.

## Licensing

This repository includes the following files which are licensed under the GNU General Public License (GPL) Version 3:

  - `requirements.in`
  - `requirements.txt`

The rest of the repository is licensed under the MIT License, which can be found in the `LICENSE` file.

### Legal Disclaimer

This project and all information herein is provided “as-is” without any warranties or representations. Axonius relies on licenses published by third parties for dependencies and background for this project and therefore does not warrant that the licenses presented herein are correct. Licensees should perform their own assessment before using this project.

### Main Project (MIT License)

All files in this repository, except for the `requirements.in` and `requirements.txt` files, are licensed under the MIT License. You can find the full text of the MIT License in the [LICENSE](LICENSE) file.

### Requirements Files (GPL License)

The `requirements.in` and `requirements.txt` files, which list the dependencies required to run this project, are licensed under the GNU General Public License (GPL). You can find the full text of the GPL in the [LICENSE-REQUIREMENTS](LICENSE-REQUIREMENTS) file.

## Known Issues

⚠️ Important Notice: Dependency Conflict (June 2025)
There is a known dependency conflict between the latest versions of the core crewai library and the embedchain library.

`crewai` (`>=0.134.0`) requires `chromadb >= 0.5.23`.

`embedchain` (and older versions of `crewai-tools` that depend on it) requires `chromadb < 0.5.0`.

These requirements are mutually exclusive.

To ensure the project remains stable and can incorporate critical security patches (like in the transformers library), the decision has been made to remove crewai-tools and embedchain as dependencies for now.

Impact on Functionality
As a result, the following pre-packaged tools are currently unavailable:

`SerperDevTool` (Internet Search)

`DirectorySearchTool`

`SeleniumScrapingTool` (Website Scraping)

`WebsiteContentQueryTool` (which relies on embedchain)

All custom tools and the core crewai agent/task/crew orchestration engine remain fully functional. This is a temporary measure pending updates from the upstream crewai and embedchain libraries.

## Prerequisites

1.  Python 3.12 (may work with other versions. Untested)

2.  Docker (optional) - to run dockerized version.

3.  Environment variables listed in [.env.example](.env.example)

### Environment Setup

The project requires certain environment variables to function correctly. You must provide a value for every variable listed in `.env.example`, even for services you do not plan to use.

1.  Copy the `.env.example` file and rename the copy to `.env`:

    ```bash
    cp .env.example .env
    ```

2.  Open the newly created `.env` file and fill in the values.

    **Note:** Due to a validation check that runs on startup, every environment variable must have a value. If you do not have credentials for a specific service (e.g., Jira, Confluence, Groq), you **must enter a placeholder value** (like "none" or "dummy_value") for its related variables to prevent the application from terminating with a configuration error.

    Make sure to keep the `.env` file secure and do not expose it publicly.

#### Environment Variables Details

**Core LLM & Tool Configuration**

*(This is where you would list variables already in `.env.example` like `OPENAI_API_KEY`, `GROQ_API_KEY`, `GITHUB_TOKEN`, etc.)*

**Jira Tools Configuration**

*These variables are mandatory at startup. Use placeholder values if you will not be using Jira tools.*

| Variable | Description | Example |
| :--- | :--- | :--- |
| `JIRA_LINK_ALLOWED_PAIRS` | Restricts ticket linking to specific project pairs. Each pair is separated by a `|`. | `PROJ1,PROJ2\|PROJ1,PROJ3` |
| `JIRA_ATTACH_ALLOWED_PREFIXES` | A comma-separated list of project prefixes where file attachments are permitted. | `PROJ,TEST` |
| `JIRA_REASSIGN_ALLOWED_PREFIXES` | A comma-separated list of project prefixes where ticket reassignments are permitted. | `PROJ,TEST` |
| `JIRA_SETPRIORITY_ALLOWED_PREFIXES`| A comma-separated list of project prefixes where priority changes are permitted. | `PROJ` |

**Azure Vision Service**

*These variables are mandatory at startup. Use placeholder values if you will not be using the `AdvancedImageAnalyzerTool`.*

| Variable | Description |
| :--- | :--- |
| `AZURE_API_KEY` | Your API key for the Azure Cognitive Services. |
| `AZURE_API_BASE` | The base endpoint URL for your Azure resource. |
| `AZURE_API_VERSION` | The API version for the Azure OpenAI service (e.g., `2024-02-01`). |
| `AZURE_OPENAI_VISION_DEPLOYMENT` | The name of your specific vision model deployment in Azure. |

## Installation

### Mac / Linux

1.  Clone the repository:

```bash
git clone https://github.com/Axonius/crews-control.git
cd crews-control
```

2.  Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

3.  Compile requirements.txt file (optional)

```bash
pip install pip-tools
pip-compile --generate-hashes requirements.in
```

4.  Install the dependencies:

```bash
pip install setuptools
pip install --require-hashes --no-cache-dir -r requirements.txt
```

#### Usage

**Run a project (interactive-mode):**

```bash
make run_it project_name=<PROJECT_TO_RUN>
```

**Run a project (cli-mode):**

```bash
python crews_control.py --project-name=<PROJECT_TO_RUN> --params input1="value 1" input2="value 2" ... inputN="value N"
```

Example - run the `pr-security-review` project to review `PR #1` of the `Axonius/crews-control` GitHub repository:

```bash
python crews_control.py --project-name pr-security-review --params github_repo_name="Axonius/crews-control" pr_number="1"
```

### Windows

Coming soon...

### Docker (tested on MacOS only)

1.  Clone the repository:

```bash
git clone https://github.com/Axonius/crews-control.git
cd crews-control
```

2.  Compile requirements.txt file (optional)

```bash
make compile-requirements
```

3.  Build the Crews-Control Docker image

```bash
make build
```

#### Usage

**Run a project (interactive-mode):**

```bash
make run_it project_name=<PROJECT_TO_RUN>
```

**Run a project (cli-mode):**

```bash
make run project_name=<PROJECT_TO_RUN> PARAMS="<input1='value 1' input2='value 2' ... inputN='value N'>"
```

Example - run the `pr-security-review` project to review `PR #1` of the `Axonius/crews-control` GitHub repository:

```bash
make run project_name=pr-security-review PARAMS="github_repo_name='Axonius/crews-control' pr_number='1'"
```

### Creating a Project

1.  Create a subfolder `projects/project_name`.
2.  Inside the subfolder, create a file named `execution.yaml`. The file can have the following structure:

```yaml
settings:
  output_results: true

user_inputs:
  user_input_1:
    title: "User input 1"
  user_input_2:
    title: "User input 2"

crews:
  data_gathering_crew:
    output_naming_template: 'output_data_gathering_{user_input_1}.md'
    agents:
      data_gatherer_agent:
        role: "Data Gatherer"
        goal: "Gather initial data based on {user_input_1} and {user_input_2}."
        tools: [human]
        backstory: "An agent that collects initial information."
    tasks:
      gather_task:
        agent: data_gatherer_agent
        description: "Collect data based on {user_input_1}."
        expected_output: "A summary of the gathered data."

  triage_crew:
    depends_on:
      - data_gathering_crew
    output_naming_template: 'output_triage_{user_input_1}.md'
    agents:
      triage_agent:
        role: "Triage Specialist"
        goal: "Analyze data and decide if a full analysis is needed."
        tools: [human]
        backstory: "An agent that makes decisions based on initial data."
    tasks:
      triage_task:
        agent: triage_agent
        description: "Analyze the output from the data gathering crew: {data_gathering_crew}. If a deep analysis is needed, your final answer must contain the phrase 'FULL_ANALYSIS_REQUIRED'."
        expected_output: "A decision string, either containing 'FULL_ANALYSIS_REQUIRED' or not."

  deep_analysis_crew:
    # FEATURE: Advanced conditional dependencies
    depends_on:
      and: # This crew runs only if BOTH conditions below are met
        - crew: data_gathering_crew # Condition 1: a simple dependency
        - crew: triage_crew # Condition 2: a dependency with a specific condition
          condition:
            output_contains: 'FULL_ANALYSIS_REQUIRED'
    output_naming_template: 'output_deep_analysis_{user_input_1}.md'
    agents:
      analysis_agent:
        role: "Analysis Expert"
        goal: "Perform a deep analysis."
        tools: [human]
        backstory: "An agent that performs in-depth analysis."
    tasks:
      analysis_task:
        agent: analysis_agent
        description: "Perform a deep and thorough analysis based on the initial data from {data_gathering_crew}."
        expected_output: "A detailed report of the findings."

  final_summary_crew:
    # depends_on can also be used structurally to ensure execution order
    depends_on:
      - deep_analysis_crew
      - triage_crew
    output_naming_template: 'output_final_summary_{user_input_1}.md'
    agents:
      summary_agent:
        role: "Summarizer"
        goal: "Create a final summary of the entire process."
        tools: [human]
        backstory: "An agent that compiles final reports."
    tasks:
      summary_task:
        agent: summary_agent
        # The description is built dynamically using a resolved input
        description: "{summary_introduction} Based on this, create a final, concise summary."
        expected_output: "A final, easy-to-read summary document."
        # FEATURE: Dynamic input resolution
        resolved_inputs:
          summary_introduction:
            case:
              # Case 1: Check if the deep analysis crew was successful
              - condition:
                  crew: deep_analysis_crew
                  status: SUCCESS
                # If so, use this value for the {summary_introduction} placeholder
                value: "A full, deep analysis was performed. The findings were: {deep_analysis_crew}"
              # Case 2: Check if the deep analysis crew was skipped
              - condition:
                  crew: deep_analysis_crew
                  status: SKIPPED
                value: "A deep analysis was not required based on the triage decision: {triage_crew}"
            # A fallback default value if no cases match
            default: "Summarize the results of the workflow."
```

### Project Folder Structure

#### Required Files and Folders

1.  **execution.yaml**:

      - **Purpose**: This is the main configuration file for the project.
      - **Contents**:
          - **Required User Inputs**: Specifies the inputs that users need to provide for the execution of the project.
          - **Context File References**: References to any context files needed for the execution.
          - **Context Subfolder**:
              - If there are references to context files in the execution.yaml, these files should be placed in a subfolder named `context`.

2.  **benchmark.yaml** (Optional):

      - **Purpose**: Used for batch processing and validation of the project.
      - **Contents**:
          - **User Input Values**: Specifies multiple runs with various user inputs. Each run includes a set of user inputs.
          - **Validations**: Includes validation details for one or more crews within the project.
              - **Metrics**: For each crew, one or more metrics are provided to compare the crew's output against the expected output.
              - **Expected Output**: This can be provided either inline within the benchmark.yaml or as a reference to a file in the `validations` subfolder.
              - **Validation Results**: The result of each validation (either success or failure) is provided as a JSON string. In case of failure, the reason is included.

#### Subfolders

1.  **context**:

      - Contains context files referenced in the execution.yaml.

2.  **validations**:

      - Contains expected output files referenced in the benchmark.yaml.
      - Stores the JSON output of each validation with a `.result` extension.

#### Example Structure

```plaintext
project-folder/
├── execution.yaml
├── benchmark.yaml (optional)
├── context/ (only if context files are referenced)
│   ├── context-file1
│   └── context-file2
└── validations/ (only if validations are included)
    ├── expected-output1 (if expected output is given as a filename reference)
    ├── expected-output2
    ├── validation1.result (JSON output of validation)
    └── validation2.result
```

  * `project-folder` is the name of the project. It resides within the [projects](projects) folder.
  * See the [execution.yaml guide](/projects/bot-generator/context/guide.md) for detailed explanation on how to create one for your project.
  * You can use the [bot-generator project](projects/bot-generator) to assist you in generating an `execution.yaml` for your project:

```sh
make run-it PROJECT_NAME=bot-generator
```

And then move it to a dedicated project folder using the helper [create-project.py](create-project.py) script:

```sh
python create-project.py <projects/bot-generator/output/generated-execution.yaml> <your-project-name>
```

### Running a project

#### Interactive mode

Interactive mode prompts the user for inputs interactively, rather than requiring them to be passed as CLI parameters or hardcoded in a configuration file. This mode is particularly useful for development or testing purposes.

To start a project in interactive mode, use the following command:

```sh
make run_it PROJECT_NAME=<your_project_name>
```

Ensure you have set up the project and provided the necessary project name.

#### CLI mode

Command Line Interface (CLI) mode enables you to run the project with specific parameters, offering more control and flexibility.

To run a project in CLI mode, use the following command:

```sh
make run PROJECT_NAME=<your_project_name> PARAMS="key1=value1 key2=value2"
```

Replace <your_project_name> with the name of your project and specify the required parameters.

#### Batch mode with benchmarking

Batch mode with benchmarking allows you to run multiple tests and benchmarks on your project to evaluate performance and efficiency.

To run the project in batch mode with benchmarking, use:

```sh
make benchmark PROJECT_NAME=<your_project_name>
```

This mode is useful for performance testing and optimizing your project.

### Development

```sh
make dev
```

This command installs development dependencies and generates a license file for all included packages.

#### Building

To build the Docker image required for running the project, use:

```sh
make build
```

This command sets up the necessary environment and dependencies for your project.

#### Compiling requirements

```sh
make compile-requirements
```

This command uses pip-tools to generate hashed requirements files for a consistent and reproducible environment.

#### Creating tools

Agents can be set up to use tools by listing them in the `_TOOLS_MAP` dictionary found in the [tools/index.py](tools/index.py) file.

Please note that due to the dependency conflict mentioned above, some pre-packaged tools from the `crewai-tools` library are temporarily unavailable. However, creating and using your own custom tools is fully supported.

You can use the [tool-generator project](projects/tool-generator) to assist you in generating a required tool:

```sh
make run-it PROJECT_NAME=tool-generator
```

### Supported LLMs and Embedders

The project supports various Large Language Models (LLMs) and embedding models. To list the available models, use the following command:

```sh
make list-models
```

This will provide a list of supported models. Make sure to check the specific configuration and compatibility of the models with your project setup. The list of supported tools and models can be expanded as needed.

## Compliance

By using the dependencies listed in `requirements.txt`, you agree to comply with the terms of the GPL for those dependencies. This means that:

  - If you distribute a derivative work that includes GPL-licensed dependencies, you must release the source code of the entire work under the GPL.
  - You must include a copy of the GPL license with any distribution of the work.

## Contribution

Contributions to the main project code should be made under the terms of the MIT License. Contributions to the `requirements.in`, `requirements.txt` files should comply with the GPL.

## Third-Party Licenses

This project uses third-party packages that are distributed under their own licenses. For a full list of these packages and their licenses, see the [LICENSES.md](LICENSES.md) file.

## Contributors

This project exists thanks to all the people who contribute. Here are some of the key contributors:

  - **Avri Schneider** ([@avri-schneider](https://github.com/avri-schneider))
      - Initial project setup, documentation and main features
  - **Ido Azulay** ([@idoazulay](https://github.com/idoazulay))
      - Initial project setup, documentation and main features
  - **Sharon Ohayon** ([@sharonOhayon](https://github.com/sharonOhayon))
      - Initial project code review and quality assurance
  - **Aviad Feig** ([@aviadFeig](https://github.com/aviadFeig))
      - Initial project documentation, presentation and training materials
  - **Alexey Shchukarev** ([@AlexeyShchukarev](https://github.com/AlexeyShchukarev))
      - Project management, code review and bugfixes
  - **Michael Goberman** ([@micgob](https://github.com/micgob))
      - Project management and team leadership

## Acknowledgements

This project builds upon the following MIT-licensed project:

  - **[crewAI](https://github.com/joaomdmoura/crewAI)** by [João Moura | crewAI™, Inc.](https://github.com/joaomdmoura/)

For a complete list of contributors, see the [CONTRIBUTORS.md](CONTRIBUTORS.md) file.
