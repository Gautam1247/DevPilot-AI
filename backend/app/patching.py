import ast
import difflib
import shutil
from pathlib import Path
from .schemas import Patch
from .security import SafeError, safe_path, source_allowed


def imports(tree):
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add('.' * node.level + (node.module or ''))
    return found


def apply_patch(original: Path, candidate: Path, patch: Patch) -> str:
    name = safe_path(patch.target_file)
    target = original / name
    if not source_allowed(name) or not target.is_file() or target.is_symlink():
        raise SafeError('Patch must target one existing non-test Python source file.')
    before = target.read_text(encoding='utf-8')
    if before.count(patch.original_code) != 1:
        raise SafeError('Original code must match exactly once; patch is missing or ambiguous.')
    after = before.replace(patch.original_code, patch.replacement_code, 1)
    if before == after or len(after.encode()) > 256 * 1024:
        raise SafeError('Patch is empty or exceeds the size limit.')
    try:
        old_tree, new_tree = ast.parse(before), ast.parse(after)
    except (SyntaxError, ValueError, RecursionError):
        raise SafeError('Patch produces invalid Python syntax.') from None
    if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and
           (n.name.startswith('test_') or n.name.startswith('Test')) for n in ast.walk(old_tree)):
        raise SafeError('Patch cannot modify a file containing test definitions.')
    if imports(new_tree) - imports(old_tree):
        raise SafeError('Patch cannot introduce new imports or dependencies.')
    # Deny newly introduced dynamic execution/import mechanisms as well.
    risky = {'eval', 'exec', '__import__', 'compile', 'import_module'}
    def dynamic_calls(tree):
        return {ast.dump(n) for n in ast.walk(tree) if isinstance(n, ast.Call) and
                ((isinstance(n.func, ast.Name) and n.func.id in risky) or
                 (isinstance(n.func, ast.Attribute) and n.func.attr in risky))}
    if dynamic_calls(new_tree) - dynamic_calls(old_tree):
        raise SafeError('Patch introduces dynamic execution or imports.')
    shutil.copytree(original, candidate)
    (candidate / name).write_text(after, encoding='utf-8', newline='')
    return ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile='a/'+name, tofile='b/'+name))
