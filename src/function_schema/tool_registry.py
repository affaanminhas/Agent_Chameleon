"""
Tool Registry — auto-discovery plugin loader
Path: function_schema/tool_registry.py

Drop any .py file with a class that has .name, .description, .execute()
into this folder and it registers automatically on next run.
"""

import os
import importlib.util
from typing import Dict, List


class ToolRegistry:

    def __init__(self):
        self.tools: Dict = {}

    def register(self, name: str, func, description: str):
        self.tools[name] = {"function": func, "description": description}

    def auto_discover(self, directory: str):
        skip = {"tool_registry.py", "__init__.py"}
        if not os.path.isdir(directory):
            print(f"   ⚠️  Tool directory not found: {directory}")
            return

        for filename in os.listdir(directory):
            if not filename.endswith(".py") or filename in skip:
                continue

            filepath    = os.path.join(directory, filename)
            module_name = filename[:-3]

            try:
                spec   = importlib.util.spec_from_file_location(module_name, filepath)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                for attr_name in dir(module):
                    attr = getattr(module, attr_name)

                    # Only look at classes, skip builtins
                    if not isinstance(attr, type):
                        continue
                    if attr_name in ("object",):
                        continue
                    # Must have an execute method defined on the class
                    if not callable(getattr(attr, "execute", None)):
                        continue

                    # Instantiate and then check instance attributes
                    try:
                        instance = attr()
                        if (
                            hasattr(instance, "name")
                            and hasattr(instance, "description")
                            and instance.name
                        ):
                            self.register(
                                name=instance.name,
                                func=instance.execute,
                                description=instance.description,
                            )
                            print(f"   ✅ Registered: {instance.name} ({filename})")
                    except Exception as e:
                        print(f"   ⚠️  Could not instantiate {attr_name} from {filename}: {e}")

            except Exception as e:
                print(f"   ⚠️  Could not load {filename}: {e}")

    def list_tools(self) -> List[str]:
        return list(self.tools.keys())

    def get_schema_as_string(self) -> str:
        lines = ["Available tools:"]
        for name, tool in self.tools.items():
            lines.append(f"  - {name}: {tool['description']}")
        return "\n".join(lines)

    def execute(self, name: str, params: Dict) -> str:
        if name not in self.tools:
            return f"Error: '{name}' not found. Available: {self.list_tools()}"
        try:
            return str(self.tools[name]["function"](**params))
        except Exception as e:
            return f"Error executing {name}: {e}"