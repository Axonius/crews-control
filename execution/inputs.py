import rich

def get_user_inputs(execution_config: dict) -> dict:
    """Get inputs from the user."""
    if 'user_inputs' not in execution_config:
        return {}

    user_inputs: dict[str, str] = {}
    for task, description in execution_config['user_inputs'].items():
        while True:
            user_input = input(f'Please enter {description["title"]}: ')
            if user_input:
                if (
                    execution_config['user_inputs'][task].get('enum') and
                    user_input not in execution_config['user_inputs'][task]['enum']
                ):
                    rich.print(
                        f'[red]Invalid {task} entered: {user_input}.'
                        f' Please enter one of {execution_config["user_inputs"][task]["enum"]}[/red]'
                    )
                    continue
                break
            if 'enum' in description:
                rich.print(
                    f'[red]Invalid {task} entered: {user_input}.'
                    f' Please enter one of {execution_config["user_inputs"][task]["enum"]}[/red]'
                )
            else:
                break
        user_inputs[task] = user_input
    rich.print(f'[white]User inputs: {user_inputs}[/white]')
    return user_inputs


def validate_user_inputs(user_inputs: dict, execution_config: dict):
    """Validate the user inputs."""
    print(f'Validating user inputs: {user_inputs} with execution config: {execution_config["user_inputs"]}')
    for user_input, descriptor in execution_config['user_inputs'].items():
        if not user_inputs.get(user_input):
            if not descriptor.get('optional'):
                raise ValueError(f'{user_input} is required')

            # set optional inputs to empty string
            user_inputs[user_input] = ''

        if (
            descriptor.get('enum') and
            user_inputs.get(user_input) not in descriptor['enum']
        ):
            raise ValueError(
                f'Invalid {user_input} entered: {user_inputs.get(user_input)}.'
                f' Please enter one of {descriptor["enum"]}'
            )
