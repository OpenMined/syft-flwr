# Development

## Publishing Python packages to PyPi

The project need to have the structure like below

```
<your_project>/
├── LICENSE
├── pyproject.toml
├── README.md
├── src/
│   └── example_package/
│       ├── __init__.py
└──   └── example.py
```

Then, in the `pyproject.toml` file, specify the build system and other things

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/"]
only-include = ["src"]
exclude = ["src/**/__pycache__"]

[tool.hatch.build.targets.sdist]
only-include = ["src", "pyproject.toml", "/README.md"]
exclude = ["src/**/__pycache__", "examples", "notebooks", "justfile"]
```

Then, go through the following steps:

1. Bump the version, e.g. `0.1.0` to `0.1.1` (minor), or `0.1.9` to `0.2.0` (major) - Tip: search for `version` in the right folder. Mostly you have to update the version in `pyproject.toml` and `__init__.py`
2. Build the project, which will create `dist/` folder

```bash
cd <your_project>
uv build .
```

3. Navigate to the `dist` folder and do some tests:
   1. Upzip the `.tar` to see the content, and also `uvx wheel unpack <path_to_whl_file>` to see the content of the `whl` file
   2. Make a new env, install the wheel with `uv pip install <path_to_whl_file>` to test things
4. Upload it to PiPy: `uvx twine upload ./dist/*`. For this, you will need to have a pypi token.
