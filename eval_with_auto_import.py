import importlib
import sys


def eval_with_auto_import(expression, globals, locals):
    while True:
        try:
            return eval(expression, globals, locals)
        except NameError as e:
            # Extract the name that's not defined
            name = str(e).split("'")[1]
            try:
                module = importlib.import_module(name)
                sys.modules[name] = module
                globals[name] = module
            except ImportError:
                raise e
