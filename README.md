# TeaWither-01 · 茶萎凋台账

Django 5 + PostgreSQL 服务端渲染应用：Templates + HTMX + 自定义 CSS，无 Vue/React SPA。

## 技术栈

- Django 5、PostgreSQL
- Session 登录
- HTMX（CDN）局部刷新列表
- Docker Compose：`web` + `db`

## 端口与数据库

| 服务 | 端口 |
|------|------|
| Web  | **4100** |
| Postgres | **5440**（容器内 5432） |

数据库账号：`teawither` / `teawither` / 库名 `teawither`

## 快速启动

```bash
cd TeaWither/TeaWither-01
docker compose up --build -d
```

浏览器打开：http://localhost:4100

演示账号：

- `admin` / `123456`（超级用户）
- `witherer` / `123456`（普通用户）

容器启动时会自动：`migrate` → `seed_data` → `collectstatic` → `gunicorn`

## 本地开发（可选）

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
# 确保本机 Postgres 监听 5440，或先 docker compose up -d db
set POSTGRES_HOST=localhost
set POSTGRES_PORT=5440
python manage.py migrate
python manage.py seed_data
python manage.py runserver 0.0.0.0:4100
```

## 业务模型

1. **Garden（茶园）**：`name`、`altitudeBand`、`notes`
2. **Trough（萎凋槽）**：归属茶园、`troughCode`、`cultivar`、`loadKg`、状态 `loading|withering|ready`；同一茶园内槽位编号唯一
3. **WitherBatch（萎凋批次）**：归属槽位、`startedAt`、`targetMoisture`、`actualMoisture`（可空）、`rollGrade`
4. **RollLink（揉捻衔接单）**：关联批次、揉捻机号 `rollerNo`、计划揉次 `plannedRolls`（可空，关闭前必须为正整数）、开单时刻 `openedAt`、关闭时刻 `closedAt`（可空）、开单人 `openedBy`

**业务规则**：将槽位状态设为 `ready`（可下槽）时，若最新批次的 `actualMoisture` 为空或大于 40，抛出中文 `ValidationError`。

### 揉捻衔接单规则

- **开单条件**：关联批次所属槽位必须为 `ready`（可下槽），且该批次已填写 `actualMoisture` 且不超过 40，否则拒绝开单（模型层校验，表单仅做预选过滤）。
- **同一批次未关闭衔接单前不可再开**：数据库有部分唯一约束 `uniq_open_roll_link_per_batch` 兜底，模型层同时校验。
- **字段锁定**：衔接单未关闭期间，该批次的 **`actualMoisture`（实测含水率）与 `rollGrade`（揉捻等级）被锁定**。锁定在 `WitherBatch.clean()` 与 `save()` 双层拦截——不仅表单禁用，直接 ORM `save()`、admin、伪造 POST 提交同样被后端拒绝；非锁定字段（如目标含水率）不受影响。衔接单关闭后两字段恢复可改。
- **关闭仅主管**：`/roll-links/<id>/close/` 仅超级用户（主管）可访问，其他用户返回 403；关闭前 `plannedRolls` 必须为正整数。
- **计数**：首页「未关闭揉捻衔接」与揉捻衔接列表的未关闭行数同口径（`closedAt IS NULL`），顶栏「揉捻衔接」带红色未关闭角标。

## 种子数据

```bash
python manage.py seed_data
```

幂等：已有茶园则只保证账号存在。亦可在环境变量 `TEAWITHER_AUTO_SEED=1` 时于 `post_migrate` 自动播种。

## 目录结构

```
TeaWither-01/
  manage.py
  requirements.txt
  Dockerfile
  entrypoint.sh
  docker-compose.yml
  config/           # 项目配置
  apps/gardens/     # 模型、视图、种子命令
  templates/        # Django 模板
  static/css/       # 自定义样式（茶绿色顶栏）
```
