# 主机 CI 模板

[English](README.md) | **简体中文**

`host-checks.yml` 包含 Ubuntu / Python 3.11 的主机检查流程：安装依赖、语法检查、6 项配置与下载测试、文档与发布内容检查、下载模型并比对独立 C 参考结果。

首次发布使用的 GitHub Personal Access Token 不含 `workflow` scope，GitHub 拒绝写入 `.github/workflows/`。因此工作流以模板形式保存在此目录，尚未自动启用。

要启用，可通过 GitHub 网页创建 `.github/workflows/ci.yml` 并复制本模板内容，或在具有工作流写入权限的本地环境执行：

```sh
mkdir -p .github/workflows
cp ci/host-checks.yml .github/workflows/ci.yml
git add .github/workflows/ci.yml
git commit -m "Enable host validation workflow"
git push
```

工作流只申请仓库内容读取权限，不读取设备配置、不执行烧录，也不包含真实 ESP32 硬件测试。对应命令可以直接在本机执行，见 [BUILD.md](../BUILD.zh-CN.md)。
