# ExportTweetsToPDF-Sdanderd (标准版)

[English Version](./README-EN.md) | 中文

## 功能

- CSV 输入 -> PDF 输出（日期 | 内容）
- 媒体下载缓存 -> 离线渲染
- 日期过滤（范围）与排序
- 基础并发（默认 4）
- 基础字体保障（中文 + 英文）
- 运行完成后自动清理媒体缓存

## Python 版本支持

- 最低支持版本：`Python 3.11`
- 推荐版本：`Python 3.12`
- 说明：`Python 3.13/3.14` 可能因部分依赖轮子与系统库差异导致安装或渲染问题，不作为标准版默认推荐环境。

## 安装

```bash
cd [Your Path]/ExportTweetsToPDF/ExportTweetsToPDF-Sdanderd
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 命令

### 1) 初始化资源（下载字体）

```bash
python tweetpdf.py --init
```

### 2) 查看版本

```bash
python tweetpdf.py --version
```

### 3) 基本导出（默认并发=4）

```bash
python tweetpdf.py --csv /path/to/TwExport_xxx_Posts.csv
```

### 4) 日期范围 + 排序

> 日期过滤必须成对输入：`--start` 和 `--end`。

```bash
python tweetpdf.py \
  --csv /path/to/TwExport_xxx_Posts.csv \
  --start 2026-01-01 \
  --end 2026-02-11 \
  --sort desc
```

## 参数

- `--csv` 输入 CSV 路径（导出时必填）
- `--out` 输出 PDF 路径（默认 CSV 同名 `.pdf`）
- `--start` 日期范围开始（YYYY-MM-DD）
- `--end` 日期范围结束（YYYY-MM-DD）
- `--sort asc|desc` 时间排序（默认 `asc`）
- `--concurrency` 媒体下载并发（默认 `4`）
- `--allow-hosts` 媒体域名白名单
- `--download-dir` 临时缓存目录（默认 `.tweetpdf_cache`）
- `--init` 初始化字体资源后退出
- `--version` 输出版本后退出
- `--help` 查看帮助

## 运行输出说明

运行中会输出阶段信息：

- 字体检查/下载
- CSV 读取与筛选
- 媒体下载
- PDF 渲染
- 缓存清理

结束会输出：

- 生成完成路径
- 清理文件数与释放空间

## 开源协议与版权

- 本项目采用 [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0) 开源协议。
- Copyright (C) 2020 - Present, TanBQ.
- 使用、修改和分发请遵循 Apache-2.0 条款。

