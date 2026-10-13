# Claude Statusline Plus

Claude Code 双行状态栏：额度使用进度、上下文用量、缓存剩余时间，以及距离上次模型响应的时间。

[English](README.md) · [上游项目](https://github.com/Astro-Han/claude-pace) · [MIT 许可证](LICENSE)

这是 **Astro-Han/claude-pace 的增强版 fork**，保留原作者署名和 MIT 许可证。新增的缓存与活动时间显示来自实际使用的 macOS / Ubuntu 配置，与 Anthropic 没有官方关联。

```text
Opus (200K) high    | my-project (main) 2f +12 -3
██░░░░░░░░ 20% 200K | 5h 25% ⇡5% 4h 0m  7d 40% ⇡12% 5d 0h  cache 2m  last 10m
```

以上是示意数据，不是任何真实账户的额度。

## 能看到什么

- 模型、上下文容量与推理强度。
- 上下文进度条，与订阅额度分开显示。
- 5 小时 / 7 天额度已用比例、重置倒计时和本地时区的重置时间。
- `⇡` / `⇣`：已用比例相对窗口已过时间的领先 / 落后，不是额度预测。
- Git 分支、文件变更与增删行数。
- `cache`：Claude Code 提供有效期时，显示缓存倒计时。
- `last`：距离主会话中上次带 API usage 的模型响应多久；工具结果不会重置这个计时。

## 安装

运行依赖：Bash 3.2+、jq、常见 Unix 工具。Git 信息需要 Git。支持 macOS 和 Linux；Windows Git Bash 保留上游路径处理，但此 fork 尚未验证。

```bash
# macOS
brew install jq
# Ubuntu / Debian
sudo apt-get install jq
```

推荐使用只修改状态栏配置的安装器，额外需要 Python 3.8+：

```bash
git clone https://github.com/VallierDev/claude-statusline-plus.git
cd claude-statusline-plus
python3 install.py
```

安装器会备份配置，安装 `~/.claude/claude-statusline-plus.sh`，只更新 `statusLine`，不修改模型、权限、账户或其他插件。默认每 60 秒刷新，等待响应时倒计时也会继续变化。

手动安装：

```bash
mkdir -p ~/.claude
cp claude-pace.sh ~/.claude/claude-statusline-plus.sh
chmod +x ~/.claude/claude-statusline-plus.sh
```

将下面字段合并到 `~/.claude/settings.json`，不要覆盖整个文件：

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/claude-statusline-plus.sh",
    "refreshInterval": 60
  }
}
```

也可以通过 Claude Code 插件安装：

```text
/plugin marketplace add VallierDev/claude-statusline-plus
/plugin install pace-statusline-plus@pace-statusline-plus-marketplace
/pace-statusline-plus:setup
```

安装后打开一个新的 Claude Code 会话。

## 为什么额度或缓存显示 `--`

额度来自 Claude Code 的 stdin `rate_limits` 字段。根据[官方文档](https://code.claude.com/docs/en/statusline)，Pro / Max 和部分网关配置会提供该数据，通常首次 API 响应后才出现；单个窗口也可能缺失。缺少数据时显示占位符，不用旧账户的缓存额度填充。

缓存倒计时读取 `prompt_cache.expires_at`，没有这个字段时不猜测有效期。`last` 只是模型活动计时，不能据此判断缓存仍然有效。新增字段已用 Claude Code 2.1.296 验证；旧版本缺少字段时会降级显示。

## 隐私

运行时脚本不发起网络请求，也不读取登录凭据。它读取 stdin 的会话 JSON 和本地设置；有 session ID 时，最多读取对应会话文件的最后 400 行，只选择模型 usage 时间戳，不输出对话内容。Git 元数据短暂缓存在用户自己的 `$XDG_RUNTIME_DIR/claude-pace` 或 `~/.cache/claude-pace`。

安装备份仅保存在本机 `~/.claude/backups/claude-statusline-plus`，使用受限权限。备份可能含你自己的私有设置，不要上传。公开仓库仅包含代码、文档及模拟数据测试。

## 卸载或恢复

删除 `settings.json` 的 `statusLine` 字段即可关闭；也可以从安装器显示的备份目录中，只恢复原来的 `statusLine` 字段。`previous-statusline.json` 记录了原字段和值。整份恢复旧设置会同时回退后来修改的其他设置，请按需要选择。之后可删除安装的 `claude-statusline-plus.sh` 文件。

## 开发与贡献

```bash
bash -n claude-pace.sh
test_home=$(mktemp -d)
HOME="$test_home" XDG_RUNTIME_DIR="" bash test.sh
python3 -m unittest discover -s tests -v
```

上游回归测试额外需要 Perl。CI 在 macOS 与 Linux 运行；新增测试覆盖缓存与额度独立显示、模型活动计时、字段缺失、异常输入，以及安装器保留其他配置。

欢迎提交 issue 或 PR。原始额度、上下文、Git 显示来自上游；新增缓存 / 活动指示、安装器与双语文档见 [CHANGELOG](CHANGELOG.md)。保留原作者署名，按 [MIT](LICENSE) 发布。
