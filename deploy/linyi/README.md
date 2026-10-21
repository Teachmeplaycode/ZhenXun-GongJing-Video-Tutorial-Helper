# linyi.work/ZhenXun

帧寻的网页版，跑在腾讯云轻量服务器（新加坡，`ubuntu@43.160.195.13`）上。

- **网关**：服务器上 `zhenyan-evidence-gateway`（Caddy）占着 80/443，也服务 mantramcp.cloud 和 aixit.club。`linyi.work` 一个项目一个路径，帧寻是 `/ZhenXun/`，以后的项目照 `linyi.work.caddy` 再加一段 `handle_path /新项目/*`。第一次加路由用 `add-route.sh`（备份、追加、校验、重载，失败自动恢复）。
- **容器**：`zhenxun`，代码在 `~/projects/zhenxun`，数据在 Docker 卷 `zhenxun_zhenxun-data`。`PUBLIC_DEMO=1`：访客隔离、不开放平台账号、只能导入 B 站和上传。
- **密钥**：`~/projects/zhenxun/deploy/linyi/.env`（只在服务器上，不进仓库），例如 `DEEPSEEK_API_KEY=…`。改完运行 `cd ~/projects/zhenxun && sudo docker compose -f deploy/linyi/compose.yaml up -d`。

## 自动部署

main 每次更新、后端和前端测试都通过后，CI 的 Deploy 任务把 `git archive HEAD backend front deploy` 通过 SSH 发给服务器。那把密钥在服务器上被限定只能运行 `receive.sh`：解包到新目录、保留 `.env`、重建并重启，健康检查不过就换回上一版。

一次性设置（在本机仓库根目录运行）：

```bash
bash deploy/linyi/setup-auto-deploy.sh
```

没设置之前，Deploy 任务会显示跳过，不影响 CI。

本机桌面版不受影响：本地用本地模型（mlx-whisper、Vision、Ollama），网页版用云端接口与服务器上的模型，靠环境变量区分。
