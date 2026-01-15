# Jupyter Notebook Setup

## What Was Done

Your devcontainer now has Jupyter notebook support with a Python kernel that has access to all your WkWorksheet modules.

### Installed Packages

Added to [requirements.txt](requirements.txt):
- `requests` - For WaniKani API calls
- `jupyter` - Jupyter notebook server
- `ipykernel` - Python kernel for Jupyter

### Registered Kernel

A Python kernel named "Python 3 (WkWorksheet)" has been registered with Jupyter. This kernel has access to:
- All standard Python libraries
- The `wkworksheet` package (your cache and config modules)
- All packages from requirements.txt

### DevContainer Configuration

Updated [.devcontainer/devcontainer.json](.devcontainer/devcontainer.json):
- Added `ms-toolsai.jupyter` VSCode extension
- Added `postCreateCommand` to auto-install packages and register kernel on container rebuild

## Using Jupyter Notebooks

### Option 1: VSCode (Recommended)

1. Open or create a `.ipynb` file (like [explore_cache.ipynb](explore_cache.ipynb))
2. Click "Select Kernel" in the top-right corner
3. Choose "Python 3 (WkWorksheet)" from the dropdown
4. Start running cells!

### Option 2: Jupyter Lab

Start Jupyter Lab from the terminal:

```bash
jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root
```

Then click the link that appears in the terminal.

### Option 3: Jupyter Notebook (Classic)

```bash
jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --allow-root
```

## Example Notebook

A sample notebook [explore_cache.ipynb](explore_cache.ipynb) has been created to demonstrate:
- Loading the WaniKani cache
- Exploring kanji by level
- Filtering subjects by various criteria
- Basic data analysis

## Verifying the Setup

Check available kernels:

```bash
jupyter kernelspec list
```

You should see:
```
Available kernels:
  wkworksheet    /root/.local/share/jupyter/kernels/wkworksheet
  python3        /usr/local/share/jupyter/kernels/python3
```

## Rebuilding the Container

If you rebuild the devcontainer, the `postCreateCommand` will automatically:
1. Install all packages from requirements.txt
2. Register the Python kernel

So everything will work out of the box!

## Example Usage in a Notebook

```python
# Import your modules
from wkworksheet.wanikani_cache import WaniKaniCache

# Initialize and fetch
cache = WaniKaniCache()
cache.fetch_subjects()

# Explore the data
kanji = cache.get_subjects("kanji")
print(f"Total kanji: {len(kanji)}")

# Filter by level
level_5_kanji = [k for k in kanji if k['data']['level'] == 5]
```

## Troubleshooting

**Kernel not found?**
- Run: `python3 -m ipykernel install --user --name=wkworksheet --display-name="Python 3 (WkWorksheet)"`

**Modules not found?**
- Make sure you're in the `/workspaces/WkWorksheet` directory
- The kernel should automatically have this in its path

**Need to reinstall packages?**
- Run: `pip install --break-system-packages -r requirements.txt`
