"""
Tool Registry — with auto-discovery
Path: src/function_schema/tool_registry.py

Drop any file with a class that has .name, .description, .execute()
into the function_schema/ folder and it registers automatically.
"""
import os
import importlib.util
from typing import Dict, List


class ToolRegistry:

    def __init__(self):
        self.tools: Dict = {}

    def register(self, name: str, func, description: str):
        """Manually register a tool."""
        self.tools[name] = {
            'function': func,
            'description': description
        }

    def auto_discover(self, directory: str):
        """
        Scan a directory and auto-register any class that has:
            .name        (str)
            .description (str)
            .execute()   (callable)

        Usage in Agent_Perry.__init__:
            self.tools.auto_discover(
                os.path.join(os.path.dirname(__file__), "function_schema")
            )
        """
        skip = {"tool_registry.py", "__init__.py"}

        if not os.path.isdir(directory):
            print(f"   ⚠️  Tool directory not found: {directory}")
            return

        for filename in os.listdir(directory):
            if not filename.endswith(".py") or filename in skip:
                continue

            filepath = os.path.join(directory, filename)
            module_name = filename[:-3]

            try:
                spec = importlib.util.spec_from_file_location(module_name, filepath)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Find all valid tool classes in the module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and attr_name not in ("object",)
                        and hasattr(attr, 'name')
                        and hasattr(attr, 'description')
                        and hasattr(attr, 'execute')
                    ):
                        try:
                            instance = attr()
                            self.register(
                                name=instance.name,
                                func=instance.execute,
                                description=instance.description
                            )
                            print(f"   ✅ Registered tool: {instance.name} (from {filename})")
                        except Exception as e:
                            print(f"   ⚠️  Could not instantiate {attr_name} from {filename}: {e}")

            except Exception as e:
                print(f"   ⚠️  Could not load {filename}: {e}")

    def list_tools(self) -> List[str]:
        return list(self.tools.keys())

    def get_schema(self) -> List[Dict]:
        return [
            {"name": name, "description": tool["description"]}
            for name, tool in self.tools.items()
        ]

    def get_schema_as_string(self) -> str:
        lines = ["Available tools:"]
        for name, tool in self.tools.items():
            lines.append(f"  - {name}: {tool['description']}")
        return "\n".join(lines)

    def execute(self, name: str, params: Dict) -> str:
        if name not in self.tools:
            return f"Error: Tool '{name}' not found. Available: {self.list_tools()}"
        try:
            return str(self.tools[name]['function'](**params))
        except Exception as e:
            return f"Error executing {name}: {e}"