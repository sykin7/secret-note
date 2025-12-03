
# Private Secure Notes (私密笔记系统)

一个轻量级的、基于 Web 的“阅后即焚”笔记服务。旨在提供最简单、安全的临时信息传递方案。

基于 Python Flask 开发，无复杂的数据库依赖，支持 Docker 容器化部署。

## ✨ 主要特性

* **阅后即焚**：笔记内容在被阅读一次后，立即从服务器数据库中物理删除，无法恢复。
* **隐私安全**：无后台管理界面，无用户追踪，无持久化日志。
* **轻量极简**：基于 SQLite 存储，无需配置 MySQL/Redis，单容器即可运行。
* **响应式设计**：完美适配 PC 端与移动端访问。
* **全中文界面**：友好的中文提示与交互流程。

## 🚀 快速开始

### 使用 Docker 部署 (推荐)

本项目支持构建为 Docker 镜像，方便在各类云平台（如 Leaflow, Sealos, Zeabur）或 VPS 上运行。

#### 1. 拉取并运行
```bash
# 请将 <your-image-name> 替换为实际的镜像名称
docker run -d -p 8787:8787 --name secure-note <your-image-name>
````

#### 2\. 访问

服务启动后，默认监听 `8787` 端口。访问 `http://localhost:8787` 即可使用。

-----

### 本地开发运行

如果你想在本地修改代码或调试：

1.  **克隆仓库**

    ```bash
    git clone [https://github.com/your-username/your-repo.git](https://github.com/your-username/your-repo.git)
    cd your-repo
    ```

2.  **安装依赖**
    建议使用 Python 3.9+ 环境。

    ```bash
    pip install -r requirements.txt
    ```

3.  **启动服务**

    ```bash
    python app.py
    ```

## 🛠️ 技术栈

  * **Backend**: Python 3, Flask
  * **Server**: Gunicorn
  * **Database**: SQLite3 (内置)
  * **Frontend**: HTML5, CSS3 (无需编译)

## ⚙️ 配置说明

| 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `PORT` | `8787` | 容器内部监听端口 |

## ⚠️ 免责声明

本项目仅供学习与私人数据传输使用。由于“阅后即焚”的特性，请勿将其作为长期存储工具。作者不对因使用本软件产生的任何数据丢失负责。

## License

MIT License.

```
```
