# Auto Green Background

[English README](./README.en.md)

基于 `Tauri + Vue + Python(OpenCV)` 的自动绿幕工具。  
输入素材图后，自动分割主体并输出固定画布大小的绿色背景图，适配模板匹配等场景。

## 功能特性

- 支持多种分割算法：`watershed` / `border-grow` / `contour` / `threshold`
- 输出固定尺寸画布（`width x height`），主体自动居中
- 实时预览，带请求合并与节流，避免频繁卡顿
- 中英文界面与参数 tooltip（hover + click）
- 自带 Python 运行时与依赖（便携包开箱即用，无需本机安装 Python）

## 本地开发

### 1) Python 环境

```bash
uv python install 3.13
uv sync
```

### 2) 前端与桌面端

```bash
npm install
npm --prefix frontend install
npm run tauri:dev
```

## 构建与打包

### 便携包（推荐）

```bash
npm run tauri:build:portable
```

产物路径：

- `dist-portable/AutoGreenBackground-win-x64-v<version>-portable.zip`

说明：

- `<version>` 默认取 `src-tauri/tauri.conf.json` 的版本号
- 在 CI/CD 中会跟随 tag（例如 `v0.1.0`）

## 性能优化说明

- 应用启动时会后台预热 bridge 子进程，降低首帧预览冷启动延迟
- Rust 与 Python 之间使用长连接（持久 bridge），不再每次预览新起进程
- 预览路径支持快速模式（下采样 + JPEG 传输），导出仍保持完整质量
- Windows 下后台 bridge 进程隐藏 cmd 窗口

## 可选 CLI（Python）

```bash
uv run python -m src.app --mode cli --input input.png --output output.png --threshold 250 --width 40 --height 40
```

## CI/CD

- CI：`.github/workflows/ci.yml`
  - Python 单元测试（Windows + Ubuntu）
  - 前端构建检查
- CD：`.github/workflows/release.yml`（`v*` tag 触发）
  - 构建 portable zip
  - 上传到 GitHub Release

发版示例：

```bash
git tag v0.1.1
git push origin v0.1.1
```
