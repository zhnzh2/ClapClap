# ClapClap 跨设备开发同步指南

## 背景

这个项目在 **Windows（当前设备）** 和 **Ubuntu 20.04（另一台设备）** 之间交替开发。两边各自有一个 Claude Code 实例，它们的对话记录和自动记忆互不相通。本文档定义了标准的同步流程。

## 涉及的文件

| 内容 | 位置 | 说明 |
|------|------|------|
| 对话记录 | `.claude/conversations/*.md` | Claude Code 对话的 Markdown 导出，一个对话一个文件 |
| 自动记忆 | `~/.claude/projects/...ClapClap.../memory/*.md` | Claude Code 的自动记忆文件（MEMORY.md + 各记忆条目） |
| 项目代码 | 整个 git 仓库 | 通过 git push/pull 同步，不在此流程范围内 |

## 工作流程

### 场景一：结束本设备开发，准备切换到另一台设备

```
第1步：git 提交代码（具体commit内容需要单独询问）
  git add -A && git commit -m "WIP: 同步点" && git push

第2步：导出 Claude 上下文
  python .claude/scripts/sync_export.py

第3步：把生成的 zip 文件传给另一台设备
  文件位置: .claude/sync/clapclap-sync-YYYYMMDD-HHmmss.zip
  传输方式任选:
    - 提交到 git（推荐）: git add .claude/sync/ && git commit -m "sync" && git push
    - U盘 / 云盘 / scp
```

### 场景二：在新设备上接手开发

```
第1步：git pull 拉取最新代码

第2步：导入 Claude 上下文
  python .claude/scripts/sync_import.py .claude/sync/clapclap-sync-*.zip

第3步：告诉 Claude 加载上下文
  把下面这段话发给 Claude:
  ---
  我刚从另一台设备导入了上下文，请先阅读 .claude/conversations/
  中的对话记录了解之前的开发对话，然后告诉我你了解到的项目状态。
  ---
```

## Claude 操作指令

**如果你是 Claude，收到用户上述请求后，请执行以下操作：**

### 步骤 A：了解项目状态

```
使用 Glob 列出 .claude/conversations/ 中的所有 .md 文件。
选择最近 2-3 个对话记录，通读它们。
总结：项目当前状态、最近在做什么、有哪些待办任务。
```

### 步骤 B：加载记忆

```
检查 ~/.claude/projects/ 下对应本项目的 memory/ 目录。
如果 MEMORY.md 存在，读取它和其中链接的所有记忆文件。
这些记忆包含用户偏好、项目约定等重要信息。
```

### 步骤 C：确认同步版本

```
运行 git log --oneline -5 确认代码版本。
对比对话记录中提到的最新提交，确认代码和对话是匹配的。
```

### 步骤 D：继续工作

```
根据了解到的状态，向用户汇报你的理解，然后继续推进未完成的任务。
```

## 脚本说明

### `sync_export.py`

导出当前设备上的 Claude 上下文为一个 zip 包：
- 自动刷新对话记录（先运行 `export_conversations.py --all`）
- 打包 `.claude/conversations/*.md`
- 打包 `~/.claude/projects/...ClapClap.../memory/*.md`
- 生成 `manifest.json` 记录导出时间、文件列表
- 输出到 `.claude/sync/clapclap-sync-YYYYMMDD-HHmmss.zip`

这个目录已被 `.gitignore` 忽略，不会自动提交。但 zip 文件可以手动提交到 git。

### `sync_import.py`

在目标设备上导入同步包：
- 解包对话记录到 `.claude/conversations/`
- 解包记忆文件到正确的 Claude Code 项目目录（自动检测路径）
- 打印导入摘要

## 注意事项

- 两台设备的项目路径不同，但脚本会自动检测 Claude Code 项目目录
- `.claude/sync/` 目录在 `.gitignore` 中，如需通过 git 传输 zip 文件，需 `git add -f .claude/sync/clapclap-sync-*.zip`
- 记忆文件可能包含用户偏好和项目约定，导入后下次对话自动生效
- 对话记录是只读参考，不会自动加载到 Claude 的上下文中——需要明确要求 Claude 阅读
- git push/pull 负责代码同步，本流程只负责 Claude 上下文的同步
