# storage — SQLite 持久化

## OVERVIEW
SQLite WAL + 仓储模式。唯一组装点是 `AppState`：connect → init_schema → 3 repos。初始化失败降级为 `None`（页面显式判空，显示"存储不可用"而非崩溃）。

## FILES

| 文件 | 职责 |
|---|---|
| `database.py` | `Database`：默认 `~/.fsa/data.db`；`init_schema` 幂等 DDL（validation_history / validation_results / chat_sessions / chat_messages / rule_overrides）+ 新增列幂等迁移（PRAGMA table_info 检测 + ALTER TABLE ADD COLUMN，含 rule_overrides.enabled 启停列）；支持 `with Database() as db` |
| `history_repo.py` | `ValidationSummary` ↔ history+results 两表（1+N 单事务提交）；`delete_older_than(days)` 保留期清理 |
| `chat_repo.py` | 会话/消息 CRUD；`add_message` 校验 role ∈ {user, assistant} |
| `override_repo.py` | 规则容差/启停覆写 UPSERT（`ON CONFLICT(rule_id) DO UPDATE`）；`get_all` 返回 `{rule_id: RuleOverride(tolerance, enabled)}`；`set` 只更新容差、`set_enabled` 只更新启停，互不覆盖 |

## INVARIANTS

- 连接配置固定，新增连接不得省略：`check_same_thread=False` + `row_factory=Row` + `PRAGMA journal_mode=WAL / busy_timeout=5000 / synchronous=NORMAL / foreign_keys=ON`
- 仓储暴露业务方法；调用方禁止写裸 SQL
- DDL 必须幂等（`CREATE TABLE IF NOT EXISTS`），`init_schema` 可重复执行；新增列一律走 `_migrate_columns`（PRAGMA table_info 检测 + ALTER TABLE ADD COLUMN，幂等且不丢旧数据）
- 时间比较用 `datetime('now','localtime',-N days)` 修饰符（与写入格式一致）
- 数据量小（~4MB），单机单用户——不引入连接池/ORM

## ANTI-PATTERNS

- 禁止在仓储外直接 `sqlite3.connect`（GUI/服务层只能经 `AppState` 拿 repo）
- 禁止在仓储方法里抛英文异常给上层
