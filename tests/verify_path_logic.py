from pathlib import Path
import sys

def resolve_dbt_path():
    # Mimic the logic to be used in the DAG
    # In the DAG, __file__ will be .../dags/most_active.py
    # Here, __file__ is .../tests/verify_path_logic.py
    # Both 'dags' and 'tests' are directories in the project root.
    # 'include' is also in the project root.

    current_file_path = Path(__file__).resolve()
    print(f"Current file: {current_file_path}")

    # 1. Try child path (Composer structure: dags/include)
    # In Composer, 'include' is inside the same directory as the DAG.
    child_path = current_file_path.parent / "include" / "dbt" / "my_project"
    print(f"Checking child path: {child_path}")

    # 2. Try sibling path (Local structure: root/dags and root/include)
    # In Local, 'include' is in the parent directory of the folder containing the DAG.
    sibling_path = current_file_path.parent.parent / "include" / "dbt" / "my_project"
    print(f"Checking sibling path: {sibling_path}")

    if child_path.exists():
        return str(child_path), "child"
    elif sibling_path.exists():
        return str(sibling_path), "sibling"
    else:
        return None, "none"

def main():
    path, path_type = resolve_dbt_path()

    if path:
        print(f"SUCCESS: Found dbt project at {path} ({path_type} match)")
        # In the local sandbox environment, we expect a 'sibling' match.
        if path_type == "sibling":
             print("Verification PASSED: Sibling path correctly identified (matches Local/Sandbox env).")
             sys.exit(0)
        else:
             # If we somehow created a child include folder in tests/, that would be weird but valid logic-wise.
             print("Verification WARNING: Found child path, but expected sibling in this env.")
             sys.exit(0)
    else:
        print("FAILURE: Could not find dbt project path.")
        sys.exit(1)

if __name__ == "__main__":
    main()
