import networkx as nx


def get_crews_execution_order(execution_config: dict) -> list[str]:
    """Get the order of execution of the crews by the 'depends_on' key.

    Structure:
    {
        'research': {}
        'crews': {
            'fetch': {
                'depends_on': ['research']
            },
            'parse': {
                'depends_on': ['fetch', 'research']
            }
        }
    }

    > The order of execution of the crews is: research, fetch, parse

    Run the crew only if the crews it depends on have been executed.
    Check that the resulted graph is Directed Acyclic Graph (DAG).
    """
    G = nx.DiGraph()
    crews = execution_config['crews']

    for crew in crews:
        G.add_node(crew)

    for crew, crew_config in crews.items():
        for dependency in crew_config.get('depends_on') or []:
            G.add_edge(dependency, crew)  # Directed edge: dependency -> crew

    if not nx.is_directed_acyclic_graph(G):
        raise nx.NetworkXUnfeasible("The graph is not a Directed Acyclic Graph (DAG).")

    execution_order = list(nx.topological_sort(G))

    return execution_order
