import toml

excludes = [
    "buildozer",
    "cython",
    "kaki",
    "psutil"
]

def is_excluded(dependency: str) -> bool:
    for exclude in excludes:
        if dependency.startswith(exclude):
            return False
    return True

def modify_pyproject_toml():
    with open("pyproject.toml", "r") as f:
        pyproject_data = toml.load(f)

    # Modify the iOS deployment target
    pyproject_data["project"]["requires"] = list(filter(is_excluded, pyproject_data["project"]["requires"]))

    with open("pyproject.toml", "w") as f:
        toml.dump(pyproject_data, f)