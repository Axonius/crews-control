# Crews Control

**Crews Control** is an abstraction layer on top of [crewAI](https://www.crewai.com/), designed to facilitate the creation and execution of AI-driven projects without writing code. By defining an `execution.yaml` file, users can orchestrate AI crews to accomplish complex tasks using predefined or custom tools.

## Features

- **No-Code AI Orchestration:** Define projects with `execution.yaml`, specifying crews, agents, and tasks.
- **Modular Tools:** Use a set of predefined tools or create custom ones.
- **Artifact Generation:** Each crew outputs a file artifact from the final task.
- **Templated Outputs:** Access outputs from previous crews’ tasks using a templating syntax.

## Licensing

### Disclaimer
TBD

### Main Project (MIT License)
All files in this repository, except for the `requirements.in` and `requirements.txt` files, are licensed under the MIT License. You can find the full text of the MIT License in the [LICENSE](LICENSE) file.

### Requirements Files (GPL License)
The `requirements.in` and `requirements.txt` files, which list the dependencies required to run this project, are licensed under the GNU General Public License (GPL). You can find the full text of the GPL in the [LICENSE-REQUIREMENTS](LICENSE-REQUIREMENTS) file.

### Why Dual Licensing?
Some dependencies listed in `requirements.in` and `requirements.txt` are licensed under the GPL. To comply with their licensing terms, these files themselves are licensed under the GPL. This ensures that users are aware of and comply with the GPL when using these dependencies.

## Prerequisites

1. Python 3.12 (may work with other versions. Untested)

2. Docker (optional) - to run dockerized version.

3. API keys listed in [.env.example](.env.example)

## Installation

### Mac / Linux

1. Clone the repository:
```bash
git clone https://github.com/Axonius/crews-control.git
cd crews-control
```

2. Create a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate
```

3. Compile requirements.txt file (optional)
```bash
pip install pip-tools
pip-compile --generate-hashes requirements.in
```

4. Install the dependencies:
```bash
pip install --require-hashes --no-cache-dir -r requirements.txt
```

#### Usage
TBD

### Windows

1. Clone the repository:
```bash
git clone https://github.com/Axonius/crews-control.git
cd crews-control
```

2. Create a virtual environment
```bash
python -m venv .venv
.venv/Scripts/activate
```

3. Compile requirements.txt file (optional)
```bash
pip install pip-tools
pip-compile --generate-hashes requirements.in
```

4. Install the dependencies:
```bash
pip install --require-hashes --no-cache-dir -r requirements.txt
```

#### Usage
TBD

### Docker

1. Clone the repository:
```bash
git clone https://github.com/Axonius/crews-control.git
cd crews-control
```

2. Compile requirements.txt file (optional)
```bash
make compile-requirements
```

3. Build the Crews-Control Docker image
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

1. Create a subfolder `projects/project_name`.
2. Inside the subfolder, create a file name `execution.yaml`. The file shall have the following structure:

```yaml
settings:
  output_results: true # controls the generation of output by each crew. TBD: consider removing.

user_inputs:
  user_input_1:
    title: "User input 1"

  user_input_2:
    title: "User input 2"

  optional_user_input_3:
    optional: true
    title: "Optional user input 3"

crews:
  some_crew:
    # can use values from user input as part of the output filename, backstory and task description
    output_naming_template: 'ouput_some_crew_filename_{user_input_1}_{user_input_2}.md'
    agents:
      some_agent:
        role: "Some Agent"
        goal: "Sample Goal based on {user_input_1} and {user_input_2}."
        tools:
          - human
        backstory: >
          This agent is a sample placeholder designed to demonstrate how AI can process and analyze data based on {user_input_1}.
        The sample data processor illustrates the capabilities of AI without being tied to a specific field.
        This placeholder can be replaced with a real agent tailored to specific project needs.    
    tasks:
      research:
        agent: some_agent
        tools:
          - human
        description: >
          This is a sample placeholder for description of a task that will be performed by some_agent.
          You can reference {user_input_1}, {user_input_2} and {optional_user_input_3}.
        expected_output: >
          This is a sample placeholder for the exected output of the sample task. You can also reference {user_input_1},
          {user_input_2} and {optional_user_input_3} here.

  some_other_crew:
    depends_on:
      - some_crew
    # can use values from user input as part of the output filename, backstory and task description
    output_naming_template: 'ouput_some_other_crew_filename_{user_input_1}_{user_input_2}.md'
    agents:
      some_agent:
        role: "Some Agent"
        goal: "Sample Goal based on {user_input_1} and {user_input_2}."
        tools:
          - human
        backstory: >
          This agent is a sample placeholder designed to demonstrate how AI can process and analyze data based on {user_input_1}.
        The sample data processor illustrates the capabilities of AI without being tied to a specific field.
        This placeholder can be replaced with a real agent tailored to specific project needs.    
    tasks:
      research:
        agent: some_agent
        tools:
          - human
        description: >
          This is a sample placeholder for description of a task that will be performed by some_agent.
          You can reference {user_input_1}, {user_input_2} and {optional_user_input_3}.

          You can also reference a dependant crew's final output like this: {some_agent}. The content of the last task of the
          referenced crew will be placed verbatim inline.
        expected_output: >
          This is a sample placeholder for the exected output of the sample task. You can also reference {user_input_1},
          {user_input_2}, {optional_user_input_3} and {some_agent} here.
```


### Project structure
### Project Folder Structure

#### Required Files and Folders

1. **execution.yaml**: 
   - **Purpose**: This is the main configuration file for the project.
   - **Contents**:
     - **Required User Inputs**: Specifies the inputs that users need to provide for the execution of the project.
     - **Context File References**: References to any context files needed for the execution.
   - **Context Subfolder**:
     - If there are references to context files in the execution.yaml, these files should be placed in a subfolder named `context`.

2. **benchmark.yaml** (Optional):
   - **Purpose**: Used for batch processing and validation of the project.
   - **Contents**:
     - **User Input Values**: Specifies multiple runs with various user inputs. Each run includes a set of user inputs.
     - **Validations**: Includes validation details for one or more crews within the project. 
       - **Metrics**: For each crew, one or more metrics are provided to compare the crew's output against the expected output. 
       - **Expected Output**: This can be provided either inline within the benchmark.yaml or as a reference to a file in the `validations` subfolder.
       - **Validation Results**: The result of each validation (either success or failure) is provided as a JSON string. In case of failure, the reason is included.

#### Subfolders

1. **context**:
   - Contains context files referenced in the execution.yaml.

2. **validations**:
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

See the [execution.yaml guide](/projects/bot-generator/context/guide.md) for detailed explanation on how to create one for your project.

### Running a project

#### Interactive mode

#### CLI mode

#### Batch mode with benchmarking

### Development

#### Building

#### Compiling requirements

#### Creating tools

### Supported LLMs and Embedders

## Compliance

By using the dependencies listed in `requirements.txt`, you agree to comply with the terms of the GPL for those dependencies. This means that:
- If you distribute a derivative work that includes GPL-licensed dependencies, you must release the source code of the entire work under the GPL.
- You must include a copy of the GPL license with any distribution of the work.

### How to Use This Project

To use this project while complying with the licenses:
1. Keep the main project code and the `requirements.txt` file separate when possible.
2. Clearly indicate which parts of your project are under the MIT license and which parts are under the GPL if you make modifications or distribute the project.

## Contribution

Contributions to the main project code should be made under the terms of the MIT License. Contributions to the `requirements.txt` file should comply with the GPL.

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
