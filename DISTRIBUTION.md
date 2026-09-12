# AIX爱客短剧工厂 V2 发布结构

V2 使用三个可独立下载的模块；同一套启动器负责检测、组合和配置，不再维护内容重复的第四份“完整版”。

AIX 项目源码以 `AGPL-3.0-only` 授权。Runtime Core、模型包和其中的第三方组件保留各自许可条款，不因与 AIX 同包发布而自动改为 AGPL。

## 1. AIX Runtime Core

包含经过验证并锁定版本的 ComfyUI、便携 Python、自定义节点、llama.cpp、FFmpeg 与启动脚本，不包含任何模型。适合首次安装和希望由 AIX 管理服务的用户。

## 2. AIX Model Packs

模型按功能拆分：H3 基础视频、Qwen 文案、资产生图、H3 质量增强。每个文件必须在模型清单中记录来源、版本、大小、SHA256、目标目录、许可证和是否允许再分发。禁止将模型提交到源码仓库。

## 3. AIX DramaFactory V2 Web

包含 Flask 后台、网页前端、工作流、静态资源、配置示例、测试和文档。Web 应用支持：

- `managed`：使用 AIX Runtime Core，按需启动和停止服务。
- `external`：连接用户已有的 ComfyUI 或 Qwen 服务；AIX 只调用接口，绝不启动、停止或更新外部服务。

## 推荐目录

```text
AIX-DramaFactory/
├─ app/                 # V2 Web应用
├─ runtime/             # Runtime Core
│  ├─ comfyui/
│  ├─ llama.cpp/
│  └─ ffmpeg/
├─ models/              # 独立公共模型库
└─ data/                # 项目、资产、输出、日志与备份
```

兼容现有整合包期间仍支持当前相对路径。新安装器应将路径写入 `config.json`，并通过 ComfyUI 的 `extra_model_paths.yaml` 连接公共模型库。

## 发布规则

1. `VERSION`、发布说明、运行核心、工作流包和模型清单必须有明确兼容关系。
2. ComfyUI 和自定义节点使用已验证的固定提交，不自动执行“全部更新”。
3. 发布前检查 `/system_stats`、`/object_info`、模型枚举、LLM `/models`、FFmpeg、端口、磁盘空间与目录写权限。
4. 默认服务只监听 `127.0.0.1`，不直接暴露 ComfyUI 或 Qwen 到公网。
5. Runtime Core、第三方节点、llama.cpp、FFmpeg、前端库和模型分别保留自己的许可证与来源声明。
6. 用户数据、API Key、项目、素材、输出、日志、缓存和备份不得进入源码或公共发布包。

## 用户入口

- **第一次使用**：启动器选择推荐组件并下载三个模块，完成校验后直接启动。
- **已有 ComfyUI**：只安装 V2 Web，在设置中选择“连接已有 ComfyUI”，通过环境检测后使用。
