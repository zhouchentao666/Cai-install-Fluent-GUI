# Cai Install - Fluent Design

[English Version](./README_EN.md)

一个基于 Fluent Design 的现代化安装工具，提供美观的用户界面和便捷的操作体验。支持多语言、主题定制、自定义仓库等高级功能。

## 🌟 项目亮点

- **现代化界面**: 基于微软 Fluent Design 设计语言
- **多语言支持**: 支持中文、英文、法语、俄语、德语
- **主题定制**: 支持深色/浅色主题，可自定义主题颜色
- **智能加速**: 自动检测并使用中国镜像加速下载
- **自定义仓库**: 支持 GitHub 和 ZIP 格式的自定义清单库
- **一键操作**: 简化的安装流程，一键完成依赖安装和程序启动

## 📸 截图展示

![](https://pub-141831e61e69445289222976a15b6fb3.r2.dev/Image_to_url_V2/-----2026-03-15-142325-imagetourl.cloud-1773555817783-iu0hay.png)

![](https://pub-141831e61e69445289222976a15b6fb3.r2.dev/Image_to_url_V2/-----2026-03-14-185223-imagetourl.cloud-1773495242612-q11k2h.png)

![https://pub-141831e61e69445289222976a15b6fb3.r2.dev/Image_to_url_V2/-----2026-03-08-205522-imagetourl.cloud-1772974647358-0kx1je.png](https://pub-141831e61e69445289222976a15b6fb3.r2.dev/Image_to_url_V2/-----2026-03-15-142325-imagetourl.cloud-1773555979061-852mv3.png)

## 社区与联系

- [GitHub 项目地址](https://github.com/zhouchentao666/Fluent-Install)
- [加入 Q 群](https://qm.qq.com/q/gtTLap5Jw4)
- [TG 群组](https://t.me/+vTrqXKpRJE9kNmVl)
- [TG 频道](https://t.me/FluentInstall)
- [Discord 服务器](https://discord.gg/2qh68QRMuA)

## 功能特点

- ✨ 现代化的 Fluent Design 界面
- 🚀 快速安装和配置
- 🌍 支持中国镜像加速
- 🛠️ 内置冲突包清理功能
- 📦 一键运行程序

## 系统要求

- Windows 10/11 操作系统
- Python 3.8 或更高版本
- 互联网连接（用于下载依赖）

## 🚄 快速开始

### 方式一：使用一键安装脚本（推荐）

1. **下载项目**或克隆仓库
2. **运行安装脚本**: 双击运行 `fluent_install.bat`
3. **选择安装方式**:
   - **标准源**: 适合网络环境良好的用户
   - **中国镜像**: 适合中国大陆用户，使用清华大学镜像加速
4. **启动程序**: 安装完成后选择「运行程序」

### 方式二：手动安装

```bash
# 1. 克隆仓库
git clone https://github.com/zhouchentao666/Fluent-Install.git

# 2. 进入项目目录
cd Fluent-Install

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行程序
python fluent_app.py
```

### 方式三：中国用户专用（镜像加速）

```bash
# 使用清华大学镜像安装依赖
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 运行程序
python fluent_app.py
```

## 🎯 使用指南

### 安装脚本菜单选项

运行 `fluent_install.bat` 后，您将看到以下选项：

| 选项  | 功能描述        | 适用场景                 |
| --- | ----------- | -------------------- |
| 1   | 安装依赖 (标准源)  | 网络环境良好的用户            |
| 2   | 安装依赖 (中国镜像) | 中国大陆用户，使用清华大学镜像      |
| 3   | 清理冲突包       | 解决依赖冲突问题             |
| 4   | 运行程序        | 启动 Fluent Design 主程序 |
| 5   | 退出          | 退出安装脚本               |

### 主程序功能

启动 `fluent_app.py` 后，您可以享受以下功能：

#### 🎨 界面特性

- **多语言界面**: 支持简体中文、English、Français、Русский、Deutsch
- **主题切换**: 深色/浅色模式，支持自定义主题颜色
- **窗口效果**: Mica、Acrylic 等现代 Windows 视觉效果
- **响应式布局**: 适配不同屏幕尺寸和分辨率

#### ⚙️ 配置选项

- **背景定制**: 支持自定义背景图片、模糊效果、饱和度调节
- **语言设置**: 自动检测系统语言或手动选择
- **主题设置**: 个性化颜色和视觉效果
- **仓库管理**: 添加和管理自定义 GitHub/ZIP 仓库

#### 🔧 高级功能

- **调试模式**: 开发者调试和故障排查
- **日志记录**: 详细的操作日志和错误追踪
- **网络代理**: 支持自定义网络配置
- **Steam 集成**: 支持自定义 Steam 安装路径

## 🔧 常见问题与解决方案

### ❓ 安装问题

#### Python 未找到或版本过低

**问题表现**: 运行脚本时提示 "Python 未找到" 或版本不符合要求
**解决方案**:

1. 访问 [Python 官网](https://www.python.org/downloads/) 下载 Python 3.8+
2. 安装时务必勾选 **"Add Python to PATH"**
3. 重启命令提示符后重试

#### 依赖安装失败

**问题表现**: pip 安装过程中出现网络错误或依赖冲突
**解决方案**:

```bash
# 1. 升级 pip
python -m pip install --upgrade pip

# 2. 清理冲突包
pip uninstall -y PyQt-Fluent-Widgets PyQt5-Fluent-Widgets PySide2-Fluent-Widgets PySide6-Fluent-Widgets

# 3. 使用中国镜像重新安装
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

### ❓ 运行问题

#### 程序启动失败或闪退

**问题表现**: 双击运行后程序立即关闭或无响应
**解决方案**:

1. **检查依赖完整性**:
   
   ```bash
   python -c "import PyQt6, qfluentwidgets, qasync" 
   ```

2. **使用调试模式启动**:
   
   ```bash
   python fluent_app.py --debug
   ```

3. **查看错误日志**: 检查程序目录下的日志文件

#### 界面显示异常

**问题表现**: 界面元素错位、字体显示异常
**解决方案**:

1. **更新显卡驱动**: 确保显卡驱动为最新版本
2. **调整 DPI 设置**: 右键程序 → 属性 → 兼容性 → 更改高 DPI 设置
3. **切换渲染模式**: 在配置文件中调整窗口效果设置

### ❓ 网络问题

#### 镜像源连接失败

**问题表现**: 中国镜像无法连接，安装缓慢
**解决方案**:

1. **切换镜像源**: 尝试其他镜像源（阿里云、豆瓣等）
2. **使用代理**: 配置系统代理或使用 VPN
3. **离线安装**: 手动下载 whl 文件后本地安装

#### GitHub 连接超时

**问题表现**: 自定义仓库无法同步
**解决方案**:

1. **配置 GitHub Token**: 在设置中添加个人访问令牌
2. **使用镜像站**: 配置 GitHub 镜像加速地址
3. **检查防火墙**: 确保防火墙未阻止程序网络访问

## 📁 项目结构

```
Fluent-Install/
├── fluent_app.py           # 🎯 Fluent Design 主程序入口
├── backend.py              # 🔧 后端逻辑处理模块
├── config.json             # ⚙️ 配置文件（主题、语言、仓库等）
├── requirements.txt        # 📦 Python 依赖包列表
├── fluent_install.bat      # 🚀 一键安装脚本（Windows）
├── run_fluent.bat          # ▶️ 快速启动脚本
├── build_exe.py            # 📦 打包工具（生成可执行文件）
└── README.md / README_EN.md # 📖 项目文档
```

### 核心文件说明

| 文件                   | 功能描述                      | 重要性   |
| -------------------- | ------------------------- | ----- |
| `fluent_app.py`      | 主程序入口，包含 Fluent Design UI | ⭐⭐⭐⭐⭐ |
| `backend.py`         | 后端逻辑，处理业务功能               | ⭐⭐⭐⭐⭐ |
| `config.json`        | 用户配置和程序设置                 | ⭐⭐⭐⭐  |
| `fluent_install.bat` | 自动化安装脚本                   | ⭐⭐⭐⭐  |
| `requirements.txt`   | 依赖包列表                     | ⭐⭐⭐   |

## 🛠️ 技术栈

### 核心框架

- **Python 3.8+**: 主要编程语言
- **PyQt6**: 跨平台 GUI 框架
- **PyQt6-Fluent-Widgets**: Fluent Design 组件库
- **qasync**: 异步编程支持

### 关键依赖

- **httpx**: 现代 HTTP 客户端
- **aiofiles**: 异步文件操作
- **ujson**: 高性能 JSON 处理
- **colorlog**: 彩色日志输出
- **vdf**: Valve 数据格式解析

### 开发工具

- **Git**: 版本控制
- **VS Code/PyCharm**: 推荐 IDE
- **Windows 10/11**: 主要开发平台

### 完整依赖列表

详见 [`requirements.txt`](requirements.txt) 文件

## 🤝 贡献指南

我们欢迎所有形式的贡献，包括代码、文档、翻译、测试等！

### 🌟 如何贡献

1. **Fork 项目**: 点击右上角的 Fork 按钮

2. **创建分支**: 为您的功能创建一个新分支
   
   ```bash
   git checkout -b feature/新功能名称
   ```

3. **提交更改**: 编写清晰的提交信息
   
   ```bash
   git commit -m "feat: 添加新功能描述"
   ```

4. **推送分支**: 将更改推送到您的 Fork
   
   ```bash
   git push origin feature/新功能名称
   ```

5. **创建 PR**: 提交 Pull Request 到主仓库

### 📝 贡献类型

- **🐛 Bug 修复**: 修复程序中的错误
- **✨ 新功能**: 添加新的功能特性
- **🌍 翻译**: 改进现有翻译或添加新语言
- **📚 文档**: 改进 README、添加教程
- **🎨 UI/UX**: 改进界面设计和用户体验
- **⚡ 性能**: 优化代码性能

### 💡 开发建议

- 遵循现有代码风格和命名规范
- 为新功能添加适当的注释和文档
- 确保所有测试都能通过
- 更新相关的 README 文档
- 在 PR 中详细描述您的更改

### 🐛 报告问题

如果您发现了 bug 或有功能建议：

1. **搜索现有 Issue**: 避免重复报告
2. **创建新 Issue**: 使用清晰的标题和详细描述
3. **提供环境信息**: 操作系统、Python 版本、错误日志等
4. **重现步骤**: 详细说明如何重现问题

## 📄 许可证

本项目采用 **MIT 许可证** 开源，您可以：

- ✅ **自由使用**: 在个人和商业项目中免费使用
- ✅ **修改源码**: 根据需求修改和定制代码
- ✅ **分发软件**: 重新分发原始或修改后的版本
- ✅ **私有使用**: 在私有项目中使用无需公开

### ⚖️ 使用条款

- **免责声明**: 本工具仅供学习和开发使用
- **合规使用**: 请遵守相关软件的使用条款和法律法规
- **风险自负**: 使用本工具产生的任何风险由用户自行承担
- **保留版权**: 分发时请注明原作者和项目链接

### 📞 联系方式

- **项目主页**: [GitHub Repository](https://github.com/zhouchentao666/Fluent-Install)
- **问题反馈**: [提交 Issue](https://github.com/zhouchentao666/Fluent-Install/issues)
- **讨论交流**: [加入社区](https://discord.gg/2qh68QRMuA)

---

## 🙏 致谢A

感谢以下开源项目和社区的支持：

- [PyQt6-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) - 精美的 Fluent Design 组件库
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - 强大的跨平台 GUI 框架
- [Python 社区](https://www.python.org/) - 提供优秀的编程语言
- [Cai-install-fluent]([pvzcxw/Cai-install-Web-GUI](https://github.com/pvzcxw/Cai-install-Web-GUI)) - 提供后端
- 所有贡献者和用户 - 让项目变得更好

⭐ 如果这个项目对您有帮助，请给我们一个 Star！
