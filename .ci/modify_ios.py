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
    project = pyproject_data["project"]
    # Modify the iOS deployment target
    project["dependencies"] = list(filter(is_excluded, project["dependencies"]))

    with open("pyproject.toml", "w") as f:
        toml.dump(pyproject_data, f)



if __name__ == "__main__":
    modify_pyproject_toml()