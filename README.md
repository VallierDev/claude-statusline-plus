# Claude Statusline Plus

Claude Code 双行状态栏与本地额度服务：显示额度和上下文用量，让 Claude 用一次简短命令查询自己的额度，并在工作检查点收到省 token 提醒。

[English](README.en.md) · [上游项目](https://github.com/Astro-Han/claude-pace) · [MIT 许可证](LICENSE)

这是 **Astro-Han/claude-pace 的增强版 fork**，保留原作者署名和 MIT 许可证。新增的缓存与活动时间显示来自实际使用的 macOS / Ubuntu 配置，与 Anthropic 没有官方关联。

```text
Opus (200K) high    | my-project (main) 2f +12 -3
██░░░░░░░░ 20% 200K | 5h 25% ⇡5% 4h 0m  7d 40% ⇡12% 5d 0h  cache 2m  last 10m
```

以上是示意数据，不是任何真实账户的额度。

## 当前会话上下文查询（1.3.0）

`/pace-statusline-plus:quota` 和 `~/.local/bin/claude-quota --compact --cwd "$PWD"` 现在同时返回上下文用量，例如 `context=63% remaining=37% capacity=1M`。JSON 的 `context_window` 包含 `status`、`used_percentage`、`remaining_percentage` 和 `context_window_size`（token 容量）。数据按会话隔离，来自 Claude Code 状态栏上报；不根据历史累计输入 token 估算当前上下文。缺失时返回 `context=unknown`，超过 180 秒没有收到数据时返回 `context=stale`。

上下文百分比与 5 小时／7 天订阅额度分开；这里显示原始上下文容量，不等同于自动压缩阈值。live hook 简报也包含这些字段，方便 Claude 提前整理进度；不会据此自动压缩或重启会话。更新后重新运行服务、插件和 live hook 安装器；已有 Claude 会话在下个工具边界采用新输出，插件命令可通过 `/reload-plugins` 加载。

## 缓存倒计时与简短保活（1.2.0）

额度命令现在同时返回 `cache=2640s`（对应状态栏的 `cache 44m`）。JSON 的 `prompt_cache` 包含 `expires_at`、`remaining_seconds` 和 `status`（`warm` / `expired` / `unknown` / `stale`）。额度重置的绝对时间仍在各窗口的 `resets_at`，与缓存到期时间分开。

启用 live hook 后，在工具调用边界检查到缓存剩余 1–300 秒，且额度建议为 `normal` 或 `conserve` 时，提醒 Claude 在下一次正常回复用最多一句话说明已完成／当前／下一步。每个缓存到期时间只提醒一次；新读数显示缓存续期后，才允许下一轮提醒。优先服从额度限制：`stop`、未知额度或未知／过期缓存不触发保活。

这里复用同一会话的正常模型回复，避免单独空发消息或创建额外定时模型任务。实际模型请求命中缓存才可能续期，读取本地服务不会续缓存；检查和回复仍可能消耗 token，没有续期成功保证。完全空闲的会话、长时间没有工具调用的会话不会被自动唤醒，所以不保证持续保温。缓存过期也不代表对话上下文消失。

更新时在仓库执行 `git pull`，然后依次运行 `python3 service/install.py`、`python3 service/install-plugin.py`、`python3 service/install-live-hook.py`。仅重载本地读数服务，不重启 Claude 会话；现有会话在下个工具边界采用新版 hook，插件命令可用 `/reload-plugins` 加载。

## 可选：新会话自动建立保活定时任务（默认关闭）

`python3 service/install-live-hook.py --keepalive` 会额外注册 SessionStart hook，并写入 `~/.local/share/claude-quota/keepalive.json`（`enabled`、`cron`，默认 `3,53 * * * *`）。每个新会话开始时，hook 只提示 Claude 用 Claude Code 内置的 CronList/CronCreate 创建一个只回复“ok”的定时任务，已有则不重复建。hook 和服务本身不联系模型、不碰令牌、不模拟输入。内置定时任务只在会话空闲时触发、7 天后过期；每次保活仍会消耗少量 token，不保证续期成功。关闭：把 `enabled` 改为 `false`。

## 能看到什么

- 模型、上下文容量与推理强度。
- 上下文进度条，与订阅额度分开显示。
- 5 小时 / 7 天额度已用比例、重置倒计时和本地时区的重置时间。
- `⇡` / `⇣`：已用比例相对窗口已过时间的领先 / 落后，不是额度预测。
- Git 分支、文件变更与增删行数。
- `cache`：Claude Code 提供有效期时，显示缓存倒计时。
- `last`：距离主会话中上次带 API usage 的模型响应多久；工具结果不会重置这个计时。

## 在 Claude Code 中使用

### 完整安装：状态栏、额度命令和服务

在本机或希望运行 Claude Code 的目标机器上执行。需要 Bash、jq、Python 3.9+ 和已安装的 Claude Code CLI；macOS 与 Linux 均支持。

```bash
git clone https://github.com/VallierDev/claude-statusline-plus.git
cd claude-statusline-plus
python3 service/install.py
python3 service/install-plugin.py
# 可选：让正在运行的会话也在工具调用时收到额度提醒
python3 service/install-live-hook.py
```

`service/install.py` 安装并启动服务，保留已有状态栏显示；没有原状态栏时使用本项目的显示脚本。`service/install-plugin.py` 安装当前 checkout 的插件命令。最后一条明确开启命令型 hook，保留已有 hooks，无需重启 Claude 进程。已有会话可输入 `/reload-plugins` 加载新插件命令；也可以在之后的新会话使用。不要在额度服务安装完成后再次运行下面的“仅安装状态栏”流程，以免替换数据转发命令。

也可以从 GitHub 插件市场安装：

```text
/plugin marketplace add VallierDev/claude-statusline-plus
/plugin install pace-statusline-plus@pace-statusline-plus-marketplace
```

市场插件提供命令和安装源码，**不会仅凭安装插件就启动额度服务**。随后告诉 Claude：“请使用此插件的 `service/install.py` 安装本地额度服务，保留当前状态栏与其他配置；再运行 `service/install-live-hook.py`，让当前会话在工作检查点收到额度提醒。”如果已按上面的 checkout 流程安装，无需重复注册另一个市场版本。

### 查询自己的额度

在 Claude Code 输入：

```text
/pace-statusline-plus:quota
```

命令使用 Claude Code 提供的当前会话 ID，返回 5 小时／7 天剩余百分比、重置倒计时和建议。读数示例（模拟数据）：

```text
5h remaining=72% reset_in=10800s; 7d remaining=60% reset_in=345600s; advice=normal; received_age=5s (reported data)
```

也可以让 Claude 在 Bash 工具中执行：

```bash
~/.local/bin/claude-quota --compact --cwd "$PWD"
```

同一目录存在多个会话时会返回 `ambiguous`；优先使用上面的插件命令。终端手动排查可用 `--list` 查看会话，再用 `--session <自己的会话ID>` 查询；不要拿别的会话读数作判断。

| 返回值 | 含义与处理 |
| --- | --- |
| `normal` | 两个窗口均有效，且没有出现下面的“超速”情况，按原任务继续 |
| `conserve` | 任一窗口已用≥80%，且剩余额度占比小于距重置的剩余时间占比（用得比均匀速度快），合并工具调用、减少重复分析 |
| `stop` | 任一窗口已用≥95%，且同样用得比均匀速度快，完成安全检查点并延期可选工作 |
| `unknown` / `stale` | 数据缺失、过期或窗口已到重置时间，不能假设额度恢复 |
| `ambiguous` | 多会话匹配，改用当前会话 ID 查询 |
| `service_unavailable` | 服务未运行或 socket 不可访问，先检查服务 |

这些是建议，不会强制终止进程。剩余百分比不是剩余 token 数。

### 可直接复制：额度、缓存保活与上下文管理提示词

完成额度服务和 live hook 安装后，把下面整段发给 Claude Code。已有会话若尚未加载插件命令，可输入 `/reload-plugins`，或使用提示词里的 Bash 查询方式。

```text
继续原任务。优先用 hook 读数；按需调用 /pace-statusline-plus:quota，避免重复查询。

- 额度按速度判断：已用≥80%且剩余额度占比<距重置剩余时间占比时省 token；≥95%同条件时安全收尾。建议回到 normal 再恢复重活。
- 缓存剩余1–300秒且额度允许：下次正常回复用一句话检查进度，同一到期时间仅一次；不空发保活。
- context≥80%：简记进度与下一步；≥90%：优先收尾。勿自行压缩、清空或重启。
- 未知、过期、会话不明不猜测；查询不会续缓存。

沿用已有定时检查，不新增定时器或 agent；完全停止后需人工唤醒。保持简短。
```

上下文 80%／90% 是这段提示词的工作建议，不是服务的强制阈值；它不会自动执行压缩。

缓存保活只在缓存有效且额度建议为 `normal` 或 `conserve` 时进行；实际模型请求命中缓存才可能续期，本地查询不会续期。若没有既有定时检查、会话已完全停止，这段提示词不会自动唤醒它，需要你再次发送继续指令。

### 省 token 等待与恢复工作

已经有定时监视／检查机制的 Claude，可以接收这段提示：

```text
在已有的定时检查中读取自己的额度：使用 /pace-statusline-plus:quota；未加载时执行 ~/.local/bin/claude-quota --compact --cwd "$PWD"。当 5 小时和 7 天窗口都有有效读数、建议（advice）为 normal 时恢复当前任务；否则继续等待。unknown、stale、ambiguous 和单纯倒计时归零，都不能作为额度已恢复的证据。不要重复创建定时器。
```

**本项目没有自动唤醒或自动续跑功能。** 如果 Claude 已经停止、没有既有定时检查，请在需要继续时发送“现在查询自己的额度，若建议（advice）为 normal，继续之前的任务”。

独立终端可以持续看读数：

```bash
~/.local/bin/claude-quota --watch --compact --interval 60
```

这个 watch 只轮询本地服务、打印变化，不消耗模型 token，也不会向 Claude 提交消息或恢复任务。不要让 Claude 把它当无限运行的阻塞工具任务。额度来源是 Claude Code 已上报的状态栏数据；状态栏定时刷新可能复用缓存，不等于向 Anthropic 查询最新余额。窗口过期后会返回未知，等待实际的新读数，不能推算为已补满。

## 仅安装状态栏

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

## 当前会话热加载（明确选择开启）

运行 `python3 service/install-live-hook.py`，增加命令型 PreToolUse/PostToolUse hook，备份配置并保留现有 hooks。Claude Code 通常会自动读取 settings 变更，使正在运行的会话在下一次工具调用边界收到额度简报。最多每分钟本地检查一次，每十分钟或建议档位改变才送入模型上下文。不会定时唤醒模型、阻止工具、修改权限、重启会话或自动恢复任务；空闲会话在下次调用工具时接收。`~/.cache/claude-quota/hook` 中回执只能证明 hook 执行，不能证明 Claude 完全遵守建议。关闭时只删除 command 指向 `quota-hook.py` 的条目，不要整份恢复旧配置覆盖后续改动。

## Claude 自查额度命令与本机服务（1.1.0）

新增 `/pace-statusline-plus:quota`：通过 Claude Code 的 `${CLAUDE_SESSION_ID}` 替换准确读取自己的会话额度，最多回复两句。终端也可以直接运行：

```bash
~/.local/bin/claude-quota --compact --cwd "$PWD"
~/.local/bin/claude-quota --list
~/.local/bin/claude-quota --compact --session <明确属于当前会话的ID>
```

服务支持 Ubuntu/Linux（systemd 用户服务）和 macOS（LaunchAgent）。在仓库目录安装：

```bash
python3 service/install.py
# 从当前 checkout 安装本地插件，避免仍加载旧版本缓存
python3 service/install-plugin.py
```

Python 3.9+、Claude Code CLI；原状态栏的运行依赖仍须满足。安装器备份相关文件，保留原状态栏命令及其他设置，只增加数据转发、用户服务和 `~/.claude/CLAUDE.md` 的额度约定；不修改 hooks、账户或权限。插件安装器只注册本插件，保留其他插件。已有会话不重启；状态栏命令变更通常会被当前 Claude Code 读取，插件命令和 CLAUDE.md 约定在新会话加载，不能保证已有会话已经接受新约定。

服务只读取状态栏 stdin 的 `session_id`、目录和 5h/7d 额度字段，写入用户私有缓存。它不读取凭据、不读取对话、不访问 Anthropic API，也不开放 TCP 端口；通过权限 `0600` 的 Unix socket 提供 `/health` 和 `/v1/quota`。Linux socket 在 `$XDG_RUNTIME_DIR/claude-quota.sock`（默认 `/run/user/<uid>/claude-quota.sock`），macOS 在 `~/.cache/claude-quota/reader.sock`。

状态栏每 60 秒转发一次；后台轮询可直接运行，不调用模型：

```bash
~/.local/bin/claude-quota --watch --compact --interval 60
```

该命令持续运行、只打印状态变化，用 Ctrl-C 停止。不要把无限循环作为 Claude 的阻塞工具任务；如需常驻输出，在独立终端运行。默认工作约定是在长任务开始和自然检查点（持续工作约每 10 分钟）执行一次查询。后台读数本身不消耗模型 token，Claude 读取结果和回复仍会消耗少量 token；没有固定 token 数保证，也没有定时唤醒模型。

返回剩余百分比和重置倒计时，不是剩余 token 数。默认建议按速度判断：每个窗口比较剩余额度占比与距重置剩余时间占比（窗口长 5 小时 / 7 天）；已用≥80% 且额度占比小于时间占比时节省，≥95% 同条件时完成安全检查点并延期可选工作；额度比时间富余（例如剩 16%、只剩一周的 4%）时照常工作。查询结果的每个窗口带 `time_remaining_percentage` 和单独的 `advice`。建议依赖 Claude 遵守，不是强制停止或自动恢复机制。多会话不合并，也不自动挑最新账户；目录匹配多条时返回 `ambiguous`，需要明确的会话 ID。缺失、超过 180 秒未收到数据或重置时间已过均返回未知，不假设额度已经补满。`received_age` 只是接收时间：定时刷新可能复用 Claude Code 缓存，服务不独立验证余额；切换账户后须等待实际响应产生对应额度再信任读数。没有任何会话上报时会显示 `unknown`。

查看服务：

```bash
# Linux
systemctl --user status claude-quota.service
# macOS
launchctl print gui/$(id -u)/com.vallierdev.claude-quota
```

Linux 用户服务退出登录后保持运行需要现有 linger 配置；安装器不会自行修改系统 linger。macOS LaunchAgent 随用户登录启动。

恢复安装器打印的备份（只恢复状态栏相关字段，不整份覆盖后来设置）：

```bash
python3 service/rollback.py ~/.claude/backups/claude-quota/<备份目录>
claude plugin uninstall pace-statusline-plus@pace-statusline-plus-local
```

服务备份和插件配置备份分别位于 `~/.claude/backups/claude-quota` 与 `~/.claude/backups/claude-quota-plugin`，可能含私有设置，不提交 Git。

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
python3 -m unittest discover -s service -p "test_*.py" -v
```

上游回归测试额外需要 Perl。CI 在 macOS 与 Linux 运行；新增测试覆盖缓存与额度独立显示、模型活动计时、字段缺失、异常输入，以及安装器保留其他配置。

欢迎提交 issue 或 PR。原始额度、上下文、Git 显示来自上游；新增缓存 / 活动指示、安装器与双语文档见 [CHANGELOG](CHANGELOG.md)。保留原作者署名，按 [MIT](LICENSE) 发布。
