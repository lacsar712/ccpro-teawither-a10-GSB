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
4. **RollLink（揉捻衔接单）**：关联批次、`rollerNo`（揉捻机号）、`plannedRolls`（计划揉次）、`openedAt`/`openedBy`（开单时刻/开单人）、`closedAt`/`closedBy`（关闭时刻/关闭人，可空）

**业务规则**：

- 将槽位状态设为 `ready`（可下槽）时，若最新批次的 `actualMoisture` 为空或大于 40，抛出中文 `ValidationError`。
- 揉捻衔接单**开单**条件（模型层 `RollLink.clean` 强制）：批次所属槽必须为「可下槽」；批次已写实测含水率且 ≤ 40%；同一批次存在未关闭衔接单时拒绝（另有数据库部分唯一索引 `uniq_open_rolllink_per_batch` 兜底）。
- 衔接单未关闭期间，该批次的**实测含水率与揉捻等级被锁定**：`WitherBatch.clean` 在后端比较库内旧值，任何保存途径（页面表单、Django Admin、shell/API）修改均抛 `ValidationError`，并非仅前端禁用。未开衔接单不会产生任何锁定。
- 衔接单**关闭仅主管**（`is_staff`，视图层 `UserPassesTestMixin`）；关闭前 `plannedRolls` 必须为正整数。关闭后批次字段恢复可改。
- 首页「未关闭衔接单」计数与衔接列表中 `closedAt` 为空的行同一查询口径；顶栏含「揉捻衔接」入口。

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
