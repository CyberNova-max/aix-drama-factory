# 参与贡献

感谢你参与 AIX 短剧工厂。项目处于快速开发阶段，当前统一开发基线为 `v2.0.0-dev.10`。

## 开发基线

开发前同步最新主分支，再创建任务分支：

```bash
git switch main
git pull
```

禁止直接在 `main` 开发。

## 功能认领

- 优先查看 GitHub Issues；较大功能没有 Issue 时先创建 Issue。
- 群内可以讨论，但认领状态、范围、验收标准和关键结论应尽量记录到 Issue。
- 在 Issue 中留言认领，避免多人重复开发同一功能。
- Bug、小优化、文档修改可以直接分支开发并提交 PR。

## 分支规则

```text
feature/功能名称
fix/问题名称
docs/文档名称
refactor/模块名称
chore/任务名称
```

原则：**一个功能 = 一个 Branch = 一个 PR**。

## Commit 规范

采用简化的 Conventional Commits：

```text
feat: 新增功能
fix: 修复问题
docs: 更新文档
refactor: 重构代码
ui: UI 调整
chore: 工程维护
```

Commit 应说明实际改变，禁止使用 `update`、`123`、`修改`、`test` 等无意义描述。

## Pull Request 规则

```text
Branch
↓
Commit
↓
Push
↓
Pull Request
↓
Review / Test
↓
Merge
↓
main
```

PR 必须说明修改内容、修改原因、涉及模块、测试情况、已知问题和关联 Issue（例如 `Closes #123`）。涉及 UI 或视频结果时，建议附截图、录屏或可复现样例。提交前请同步最新 `main`。

## main 原则

`main` 应尽量始终保持：

- 可以正常启动；
- 核心功能正常；
- 不包含明显实验性残缺代码；
- 不包含 API Key、Token、密码、Cookie、私钥、用户数据或本机配置。

所有正式修改原则上通过 PR 合并。紧急修复也应尽快补齐 Issue、测试与说明。

## 大改动规则

以下修改先通过 Issue 或群内讨论确认范围，随后仍通过 PR 合并：

- 架构、API 或数据结构大改；
- 删除已有功能；
- 修改核心模型或工作流；
- 大规模 UI 重构；
- 目录结构或部署方式调整；
- 影响现有项目兼容性、升级或回滚的改动。

## 测试与安全

提交前应运行相关测试，确认项目可启动或说明未能验证的原因，并检查 `git status` 和完整 diff。不得提交 `.env`、`config.json`、凭据、用户项目、素材、成片、模型、日志、备份或本机绝对路径。

不要把真实 Secret 放进 Issue、PR、截图或日志。安全漏洞请按 [SECURITY.md](SECURITY.md) 私下报告。

## 许可证

提交贡献即表示你有权提交相关内容，并同意该贡献按项目的 `AGPL-3.0-only` 许可证发布。第三方代码、模型、素材或工作流必须注明来源和许可证，不会自动适用本项目许可证。
