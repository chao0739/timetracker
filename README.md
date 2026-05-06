# 时间追踪器 v2

支持自定义时区、番茄钟、为未来上云做好分层准备的时间追踪 TUI 程序。

## 项目结构

```
timetracker_v2/
├── run.py                    # 启动入口
└── timetracker/
    ├── __init__.py
    ├── db.py                 # 数据访问层 (SQL only, 所有表带 user_id)
    ├── service.py            # 业务逻辑层 (无 UI, 未来 Web 直接复用)
    ├── tui.py                # TUI 界面 (Textual)
    └── main.py               # 装配入口
```

**为什么这么分？** `service.py` 不依赖任何 UI 库，未来要上云：
- 把 `db.py` 换成 SQLAlchemy + PostgreSQL（改一个文件）
- 写一个 `api.py`（FastAPI 路由），每个路由调用同一个 `TimerService` 方法
- 前端写 Web/移动端 UI
- `tui.py` 可以保留也可以删，互不影响

数据库每张表都有 `user_id`，本地版固定为 1。上云时改成真实用户 ID 即可，**老数据零迁移成本**。

## 安装与运行

```bash
pip install textual rich
cd timetracker_v2
python run.py
```

## 快捷键

### 计时器
| 键 | 功能 |
|---|---|
| `n` | 新建计时器 |
| `空格` | 启动 / 暂停选中计时器（支持多个并行） |
| `r` | 重命名 |
| `d` | 删除（有确认） |
| `e` | 导出会话 CSV |

### 时区
| 键 | 功能 |
|---|---|
| `t` | 打开时区管理（在弹窗里 `a` 添加 / `d` 删除 / `Esc` 关闭） |

第一个时区（标 ★）是统计周期的基准——「今日 / 本周 / 本月」按它的零点界定。

### 番茄钟
| 键 | 功能 |
|---|---|
| `p` | 启动一个工作番茄 |
| `x` | 取消当前番茄（记录为未完成） |
| `c` | 番茄钟设置（工作/短休/长休时长、长休间隔、响铃开关） |

### 其他
| 键 | 功能 |
|---|---|
| `q` | 退出 |

## 番茄钟说明

- **独立功能**：和普通计时器并行存在，互不影响
- **自定义时长**：默认 25 分钟工作 / 5 分钟短休 / 15 分钟长休 / 4 个工作番茄后长休一次
- **完成时双重提醒**：终端响铃（`\a`）+ 状态栏弹出通知；响铃可在设置里关掉
- **完成的番茄记录入库**：`pomodoros` 表，可以用来后续做统计
- **中途取消**：会被记录为 `completed=0`，不计入今日完成数

## 时区管理

任意添加 IANA 时区，比如：
- `Europe/Paris`
- `Asia/Shanghai`
- `America/New_York`
- `Asia/Tokyo`
- `UTC`

添加时按关键词搜索（不区分大小写），匹配项多的话弹出选择列表。
顶部时钟栏会按你配置的时区数量自动横向铺开。

## 数据存储

- 路径：`~/.timetracker.db`
- 备份：`cp ~/.timetracker.db backup.db`
- 表：
  - `users` — 用户表
  - `user_prefs` — 用户偏好（时区列表、番茄钟配置都在这里，key-value 结构方便扩展）
  - `timers` — 计时器主表
  - `sessions` — 计时会话日志（每次启停一条）
  - `pomodoros` — 番茄钟会话日志

## 异常恢复

- 每 10 秒自动 checkpoint 运行中的计时器到数据库
- 程序崩溃 / 断电时，最多丢失最后 10 秒
- 下次启动会自动检测并恢复，状态栏会提示

## 上云改造路径（未来参考）

按改动量从小到大：

1. **数据库换 PostgreSQL**：改 `db.py` 的连接和 SQL 方言（推荐用 SQLAlchemy 改一次到位，约 200 行）
2. **加 Web API**：新增 `api.py`，FastAPI 路由调用 `TimerService` 方法。每个路由从 JWT 取 `user_id` 传入即可
3. **加认证**：FastAPI + python-jose 做 JWT，加注册/登录路由
4. **前端**：你想用什么框架都行，REST API 是标准的
5. **Checkpoint 机制改造**：客户端不再负责 checkpoint，改成服务端按"上次心跳时间"截断；或者干脆删除 checkpoint 逻辑，启动→停止一次性结算（停止时由客户端调 API 通知）

`service.py` 里的 `TimerService` 是核心资产，上云时基本不用改业务逻辑——这是分层的最大价值。
