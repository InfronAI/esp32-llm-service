# Host CI template

**English** | [简体中文](README.zh-CN.md)

`host-checks.yml` defines an Ubuntu / Python 3.11 workflow: install dependencies, check syntax, run six configuration/download tests, check documentation and publication content, download the model, and compare the independent C reference result.

The GitHub Personal Access Token used for initial publication lacked the `workflow` scope, so GitHub rejected writes to `.github/workflows/`. The workflow is therefore stored here as a template and is not enabled automatically.

To enable it, create `.github/workflows/ci.yml` through the GitHub website and paste the template, or use a local environment with workflow write permission:

```sh
mkdir -p .github/workflows
cp ci/host-checks.yml .github/workflows/ci.yml
git add .github/workflows/ci.yml
git commit -m "Enable host validation workflow"
git push
```

The workflow requests only repository-content read access. It does not read device configuration, flash hardware, or test a physical ESP32. The same checks can run locally; see [BUILD.md](../BUILD.md).
