from importlib.metadata import entry_points

from .engine import Planner


def discover_plugins():
    plugins = {}
    for point in entry_points(group="nexus_atom.plugins"):
        if point.name in plugins:
            raise ValueError(f"Duplicate plugin entry point: {point.name}")
        plugins[point.name] = point
    return plugins


class PluginPlanner(Planner):
    def __init__(self, plugin):
        self.plugin = plugin

    async def plan(self, goal, history, registry):
        return await self.plugin.plan(goal, history, registry)
