# Crews Control

**Crews Control** is an abstraction layer on top of CrewAI, designed to facilitate the creation and execution of AI-driven projects without writing code. By defining an `execution.yaml` file, users can orchestrate AI crews to accomplish complex tasks using predefined or custom tools.

## Features

- **No-Code AI Orchestration:** Define projects with `execution.yaml`, specifying crews, agents, and tasks.
- **Modular Tools:** Use a set of predefined tools or create custom ones.
- **Artifact Generation:** Each crew outputs a file artifact from the final task.
- **Templated Outputs:** Access outputs from previous crews’ tasks using a templating syntax.

## Getting Started

### Installation

```bash
# Clone the repository
git clone https://github.com/Axonius/crews-control.git
cd crews-control

# Install dependencies
pip install -r requirements.txt
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
  - Project management
- **Michael Goberman** ([@micgob](https://github.com/micgob))
  - Project management and team leadership

## Acknowledgements


This project builds upon the following MIT-licensed project:

- **[crewAI](https://github.com/joaomdmoura/crewAI)** by [João Moura | crewAI™, Inc.](https://github.com/joaomdmoura/) 

For a complete list of contributors, see the [CONTRIBUTORS.md](CONTRIBUTORS.md) file.

## TBD
Documentation

## License
Crews-Control is released under the [MIT License](LICENSE).

## Third-Party Licenses

This project uses third-party packages that are distributed under their own licenses. For a full list of these packages and their licenses, see the [LICENSES.md](LICENSES.md) file.
