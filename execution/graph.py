import networkx as nx
import typing

def _extract_crew_names_recursive(dependency_block: any) -> list[str]:
    """Recursively traverses the dependency structure to extract all crew names."""
    crew_names = []
    if isinstance(dependency_block, str):
        return [dependency_block]
    
    if isinstance(dependency_block, list): # For backward compatibility
        for item in dependency_block:
            crew_names.extend(_extract_crew_names_recursive(item))
        return crew_names

    if isinstance(dependency_block, dict):
        if 'crew' in dependency_block:
            return [dependency_block['crew']]
        
        # Look for logical operators
        for operator in ['and', 'or']:
            if operator in dependency_block:
                for operand in dependency_block[operator]:
                    crew_names.extend(_extract_crew_names_recursive(operand))
                return crew_names
    return []

def get_crews_execution_order(execution_config: dict) -> list[str]:
    """Get the order of execution of the crews by the 'depends_on' key.

    This function parses the `depends_on` key to build a dependency graph and
    determines the correct execution order using a topological sort. It is designed
    to be backward-compatible, supporting both a simple list format and a more
    expressive nested dictionary format for complex logical dependencies.

    NOTE: This function is only responsible for establishing the execution *order*.
    It extracts all crew names mentioned in `depends_on` to build the graph.
    The actual evaluation of any conditions (`contains`, `and`, `or`, etc.)
    is handled by the orchestrator at runtime.

    ---
    
    ### Structure Examples ###

    **1. Simple List (Unconditional `and`)**

    The original format, where all listed crews must be executed first.

    ```yaml
    crews:
      fetch:
        depends_on: ['research']
      parse:
        depends_on: ['fetch', 'research']
    ```
    > A valid execution order would be: `['research', 'fetch', 'parse']`

    **2. Advanced Dictionary (Nested `and`/`or` Logic)**
    
    The new format, allowing for complex dependency checks. This function will
    extract `triage`, `fetch_data_A`, and `fetch_data_B` as dependencies
    to determine the order, while ignoring the condition logic itself.

    ```yaml
    crews:
      generate_report:
        depends_on:
          and:
            - crew: triage
              condition: {'not_contains': 'NO_THREAT_MODELING_NEEDED'}
            - or:
                - crew: fetch_data_A
                - crew: fetch_data_B
    ```
    > A valid execution order could be: `['triage', 'fetch_data_A', 'fetch_data_B', 'generate_report']`
    (assuming fetch_data_A and fetch_data_B have no dependencies and can run in parallel with triage).

    ---

    The primary purpose is to run the crew only if the crews it depends on have
    been executed and to check that the resulting graph is a Directed Acyclic
    Graph (DAG).
    """
    G = nx.DiGraph()
    crews = execution_config['crews']

    for crew in crews:
        G.add_node(crew)

    for crew, crew_config in crews.items():
        dependencies = crew_config.get('depends_on')
        if not dependencies:
            continue

        # Use the recursive helper to get a flat list of all dependency names
        dependency_list = _extract_crew_names_recursive(dependencies)
        
        for dependency in dependency_list:
            # It's good practice to ensure the dependency is a valid crew before adding an edge
            if dependency in crews:
                G.add_edge(dependency, crew)  # Directed edge: dependency -> crew

    if not nx.is_directed_acyclic_graph(G):
        cycle_details = " -> ".join(nx.find_cycle(G, orientation='original')[0])
        raise nx.NetworkXUnfeasible(f"The graph is not a Directed Acyclic Graph (DAG). A cycle was found: {cycle_details}")

    execution_order = list(nx.topological_sort(G))

    return execution_order
