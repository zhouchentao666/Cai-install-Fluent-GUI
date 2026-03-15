# Cai Install - Fluent Design

A modern installation tool based on Fluent Design, providing a beautiful user interface and convenient operation experience. Supports multi-language, theme customization, custom repositories and other advanced features.

## 🌟 Project Highlights

- **Modern Interface**: Based on Microsoft Fluent Design language
- **Multi-language Support**: Supports Chinese, English, French, Russian, German
- **Theme Customization**: Dark/light mode with custom theme colors
- **Smart Acceleration**: Auto-detect and use China mirror for faster downloads
- **Custom Repositories**: Support for GitHub and ZIP format custom repositories
- **One-click Operation**: Simplified installation process with one-click dependency installation and program launch

## 📸 Screenshots

![](https://pub-141831e61e69445289222976a15b6fb3.r2.dev/Image_to_url_V2/-----2026-03-15-142325-imagetourl.cloud-1773555817783-iu0hay.png)

![](https://pub-141831e61e69445289222976a15b6fb3.r2.dev/Image_to_url_V2/-----2026-03-15-144111-imagetourl.cloud-1773556925932-gkvose.png)

![https://pub-141831e61e69445289222976a15b6fb3.r2.dev/Image_to_url_V2/-----2026-03-08-205522-imagetourl.cloud-1772974647358-0kx1je.png](https://pub-141831e61e69445289222976a15b6fb3.r2.dev/Image_to_url_V2/-----2026-03-15-142325-imagetourl.cloud-1773555979061-852mv3.png)

[中文版本](./README.md)

## Community & Contact

- [GitHub Repository](https://github.com/zhouchentao666/Fluent-Install)
- [Join QQ Group](https://qm.qq.com/q/gtTLap5Jw4)
- [Telegram Group](https://t.me/+vTrqXKpRJE9kNmVl)
- [Telegram Channel](https://t.me/FluentInstall)
- [Discord Server](https://discord.gg/2qh68QRMuA)

## 🚀 Features

- ✨ Modern Fluent Design interface
- 🌍 Multi-language support (Chinese, English, French, Russian, German)
- 🎨 Theme customization (dark/light mode, custom theme colors)
- 🚀 Smart network acceleration (auto-detect and use China mirror)
- 🛠️ One-click dependency installation and conflict cleanup
- 📦 Custom repository support (GitHub and ZIP formats)
- ⚙️ Rich configuration options (background images, blur effects, layout)
- 🔧 Developer-friendly (debug mode, logging support)

## 📋 System Requirements

- **Operating System**: Windows 10/11 (64-bit)
- **Python Version**: 3.8 or higher
- **Runtime Environment**: Internet connection required (for dependencies and updates)
- **Hardware Requirements**: Minimum 4GB RAM, 8GB or higher recommended
- **Storage Space**: At least 500MB available disk space

## 🚄 Quick Start

### Method 1: One-click Installation Script (Recommended)

1. **Download the project** or clone the repository
2. **Run installation script**: Double-click `fluent_install.bat`
3. **Choose installation method**:
   - **Standard Source**: For users with good network environment
   - **China Mirror**: For mainland China users, using Tsinghua University mirror acceleration
4. **Launch program**: Select "Run Program" after installation completes

### Method 2: Manual Installation

```bash
# 1. Clone repository
git clone https://github.com/zhouchentao666/Fluent-Install.git

# 2. Enter project directory
cd Fluent-Install

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run program
python fluent_app.py
```

### Method 3: For China Users (Mirror Acceleration)

```bash
# Use Tsinghua University mirror to install dependencies
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# Run program
python fluent_app.py
```

## 🎯 Usage Guide

### Installation Script Menu Options

After running `fluent_install.bat`, you will see the following options:

| Option | Function Description                | Applicable Scenario                         |
| ------ | ----------------------------------- | ------------------------------------------- |
| 1      | Install Dependencies (Standard)     | Users with good network environment         |
| 2      | Install Dependencies (China Mirror) | Mainland China users, using Tsinghua mirror |
| 3      | Clean Conflict Packages             | Resolve dependency conflicts                |
| 4      | Run Program                         | Launch Fluent Design main program           |
| 5      | Exit                                | Exit installation script                    |

### Main Program Features

After launching `fluent_app.py`, you can enjoy the following features:

#### 🎨 Interface Features

- **Multi-language Interface**: Supports Simplified Chinese, English, Français, Русский, Deutsch
- **Theme Switching**: Dark/light mode with custom theme colors
- **Window Effects**: Mica, Acrylic and other modern Windows visual effects
- **Responsive Layout**: Adapts to different screen sizes and resolutions

#### ⚙️ Configuration Options

- **Background Customization**: Support for custom background images, blur effects, saturation adjustment
- **Language Settings**: Auto-detect system language or manual selection
- **Theme Settings**: Personalized colors and visual effects
- **Repository Management**: Add and manage custom GitHub/ZIP repositories

#### 🔧 Advanced Features

- **Debug Mode**: Developer debugging and troubleshooting
- **Logging**: Detailed operation logs and error tracking
- **Network Proxy**: Support for custom network configuration
- **Steam Integration**: Support for custom Steam installation path

## 🔧 Common Issues and Solutions

### ❓ Installation Issues

#### Python Not Found or Version Too Low

**Issue**: Prompt "Python not found" or version doesn't meet requirements when running script
**Solutions**:

1. Visit [Python Official Website](https://www.python.org/downloads/) to download Python 3.8+
2. Make sure to check **"Add Python to PATH"** during installation
3. Restart command prompt and retry

#### Dependency Installation Failed

**Issue**: Network errors or dependency conflicts during pip installation
**Solutions**:

```bash
# 1. Upgrade pip
python -m pip install --upgrade pip

# 2. Clean conflict packages
pip uninstall -y PyQt-Fluent-Widgets PyQt5-Fluent-Widgets PySide2-Fluent-Widgets PySide6-Fluent-Widgets

# 3. Reinstall using China mirror
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

### ❓ Runtime Issues

#### Program Fails to Start or Crashes

**Issue**: Program closes immediately or becomes unresponsive after double-clicking
**Solutions**:

1. **Check dependency integrity**:
   
   ```bash
   python -c "import PyQt6, qfluentwidgets, qasync" 
   ```

2. **Launch in debug mode**:
   
   ```bash
   python fluent_app.py --debug
   ```

3. **Check error logs**: Review log files in the program directory

#### Interface Display Abnormalities

**Issue**: Interface elements misaligned, font display issues
**Solutions**:

1. **Update graphics drivers**: Ensure graphics drivers are up to date
2. **Adjust DPI settings**: Right-click program → Properties → Compatibility → Change high DPI settings
3. **Switch rendering mode**: Adjust window effect settings in configuration file

### ❓ Network Issues

#### Mirror Source Connection Failed

**Issue**: China mirror cannot connect, installation is slow
**Solutions**:

1. **Switch mirror sources**: Try other mirror sources (Alibaba Cloud, Douban, etc.)
2. **Use proxy**: Configure system proxy or use VPN
3. **Offline installation**: Manually download whl files for local installation

#### GitHub Connection Timeout

**Issue**: Custom repositories cannot sync
**Solutions**:

1. **Configure GitHub Token**: Add personal access token in settings
2. **Use mirror sites**: Configure GitHub mirror acceleration address
3. **Check firewall**: Ensure firewall doesn't block program network access

## 📁 Project Structure

```
Fluent-Install/
├── fluent_app.py           # 🎯 Fluent Design main program entry
├── backend.py              # 🔧 Backend logic processing module
├── config.json             # ⚙️ Configuration file (theme, language, repositories)
├── requirements.txt        # 📦 Python dependency package list
├── fluent_install.bat      # 🚀 One-click installation script (Windows)
├── run_fluent.bat          # ▶️ Quick launch script
├── build_exe.py            # 📦 Packaging tool (generate executable)
└── README.md / README_EN.md # 📖 Project documentation
```

### Core File Description

| File                 | Function Description                          | Importance |
| -------------------- | --------------------------------------------- | ---------- |
| `fluent_app.py`      | Main program entry, contains Fluent Design UI | ⭐⭐⭐⭐⭐      |
| `backend.py`         | Backend logic, handles business functions     | ⭐⭐⭐⭐⭐      |
| `config.json`        | User configuration and program settings       | ⭐⭐⭐⭐       |
| `fluent_install.bat` | Automated installation script                 | ⭐⭐⭐⭐       |
| `requirements.txt`   | Dependency package list                       | ⭐⭐⭐        |

## 🛠️ Technology Stack

### Core Framework

- **Python 3.8+**: Main programming language
- **PyQt6**: Cross-platform GUI framework
- **PyQt6-Fluent-Widgets**: Fluent Design component library
- **qasync**: Asynchronous programming support

### Key Dependencies

- **httpx**: Modern HTTP client
- **aiofiles**: Asynchronous file operations
- **ujson**: High-performance JSON processing
- **colorlog**: Color log output
- **vdf**: Valve data format parsing

### Development Tools

- **Git**: Version control
- **VS Code/PyCharm**: Recommended IDEs
- **Windows 10/11**: Main development platform

### Complete Dependency List

See [`requirements.txt`](requirements.txt) file for details

## 🤝 Contribution Guidelines

We welcome all forms of contribution, including code, documentation, translation, testing, and more!

### 🌟 How to Contribute

1. **Fork the project**: Click the Fork button in the upper right corner

2. **Create branch**: Create a new branch for your feature
   
   ```bash
   git checkout -b feature/new-feature-name
   ```

3. **Submit changes**: Write clear commit messages
   
   ```bash
   git commit -m "feat: Add new feature description"
   ```

4. **Push branch**: Push changes to your Fork
   
   ```bash
   git push origin feature/new-feature-name
   ```

5. **Create PR**: Submit Pull Request to main repository

### 📝 Types of Contributions

- **🐛 Bug Fixes**: Fix errors in the program
- **✨ New Features**: Add new functional features
- **🌍 Translation**: Improve existing translations or add new languages
- **📚 Documentation**: Improve README, add tutorials
- **🎨 UI/UX**: Improve interface design and user experience
- **⚡ Performance**: Optimize code performance

### 💡 Development Suggestions

- Follow existing code style and naming conventions
- Add appropriate comments and documentation for new features
- Ensure all tests pass
- Update related README documentation
- Describe your changes in detail in the PR

### 🐛 Reporting Issues

If you find bugs or have feature suggestions:

1. **Search existing Issues**: Avoid duplicate reports
2. **Create new Issue**: Use clear titles and detailed descriptions
3. **Provide environment information**: Operating system, Python version, error logs, etc.
4. **Reproduction steps**: Explain in detail how to reproduce the issue

## 📋 Version History

### v2.5 (Current Version)

- ✨ Added multi-language support (5 languages)
- 🎨 Improved Fluent Design interface
- ⚙️ Added theme customization features
- 🔧 Optimized installation script and error handling
- 📦 Added support for custom GitHub/ZIP repositories

### v2.0

- 🚀 Rewrote core architecture, improved performance
- 🌍 Added China mirror acceleration support
- 🛠️ Improved dependency management and conflict resolution
- 📱 Optimized mobile responsive design

### v1.0

- 🎯 Initial version release
- ✨ Basic Fluent Design interface
- 🔧 Core functionality implementation

---

## 🙏 Acknowledgments

Thanks to the following open source projects and communities for their support:

- [PyQt6-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) - Beautiful Fluent Design component library
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - Powerful cross-platform GUI framework
- [Python Community](https://www.python.org/) - Provides excellent programming language
- [Cai-install-fluent]([pvzcxw/Cai-install-Web-GUI](https://github.com/pvzcxw/Cai-install-Web-GUI)) - Provides backend
- All contributors and users - Making the project better

⭐ If this project is helpful to you, please give us a Star!
