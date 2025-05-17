// 简化版本的Electron主进程
const { app, BrowserWindow, ipcMain, dialog, globalShortcut } = require('electron');
const path = require('path');
const isDev = require('electron-is-dev');
const { spawn } = require('child_process');
const fs = require('fs');

// 保持对窗口对象的全局引用
let mainWindow;
let backendProcess = null;
// 主题模式
let isDarkMode = false;

// 创建主窗口
function createWindow() {
  console.log('创建主窗口');

  // 创建浏览器窗口
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    // 隐藏默认菜单栏
    autoHideMenuBar: true,
    menuBarVisible: false,
    // 设置窗口背景色为白色（默认日间模式）
    backgroundColor: '#ffffff'
  });

  // 完全移除菜单栏
  mainWindow.setMenu(null);

  // 高级文件拖放处理 - 全面增强版
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (url.startsWith('file://')) {
      event.preventDefault();
      console.log('拦截到文件拖放导航事件:', url);

      // 解析文件路径
      let filePath = '';
      if (process.platform === 'win32') {
        // Windows: file:///C:/path/to/file.usd
        filePath = decodeURIComponent(url.replace(/^file:\/\/\//, ''));
      } else {
        // macOS/Linux: file:///path/to/file.usd
        filePath = decodeURIComponent(url.replace(/^file:\/\//, ''));
      }

      console.log('解析后的文件路径:', filePath);

      // 发送到渲染进程
      mainWindow.webContents.send('file-dropped', {
        path: filePath,
        name: path.basename(filePath),
        url: url,
        source: 'will-navigate'
      });
    }
  });

  // 监听文件拖放事件 - 使用will-navigate和drop事件双重保障
  mainWindow.webContents.on('did-finish-load', () => {
    console.log('注入高级拖放处理脚本');

    // 注入增强版拖放处理脚本
    mainWindow.webContents.executeJavaScript(`
      // 防止默认拖放行为
      document.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();

        // 添加视觉反馈
        const dropZone = document.querySelector('[data-dropzone="true"]');
        if (dropZone) {
          dropZone.classList.add('drag-active');
        }
      });

      // 拖放离开时移除视觉反馈
      document.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();

        const dropZone = document.querySelector('[data-dropzone="true"]');
        if (dropZone) {
          dropZone.classList.remove('drag-active');
        }
      });

      // 处理文件拖放
      document.addEventListener('drop', (e) => {
        console.log('捕获到文件拖放事件');
        e.preventDefault();
        e.stopPropagation();

        // 移除视觉反馈
        const dropZone = document.querySelector('[data-dropzone="true"]');
        if (dropZone) {
          dropZone.classList.remove('drag-active');
        }

        // 检查是否有文件
        if (e.dataTransfer.files.length > 0) {
          const file = e.dataTransfer.files[0];
          console.log('拖放的文件:', file.name);

          // 收集所有可能的路径信息
          const fileData = {
            name: file.name,
            size: file.size,
            type: file.type,
            lastModified: file.lastModified,
            source: 'drop-event'
          };

          // 尝试获取路径 - 使用多种方法
          if (file.path) {
            fileData.path = file.path;
            console.log('从file.path获取路径:', file.path);
          }

          if (file.webkitRelativePath) {
            fileData.webkitRelativePath = file.webkitRelativePath;
            console.log('从webkitRelativePath获取路径:', file.webkitRelativePath);
          }

          // 尝试从DataTransfer获取更多信息
          try {
            if (e.dataTransfer.getData('text/uri-list')) {
              fileData.uriList = e.dataTransfer.getData('text/uri-list');
              console.log('从URI列表获取:', fileData.uriList);
            }

            if (e.dataTransfer.getData('text/plain')) {
              fileData.textPlain = e.dataTransfer.getData('text/plain');
              console.log('从text/plain获取:', fileData.textPlain);
            }
          } catch (err) {
            console.warn('获取DataTransfer数据时出错:', err);
          }

          // 通知主进程处理文件
          if (window.electron && window.electron.handleDroppedFile) {
            console.log('调用handleDroppedFile API处理文件');
            window.electron.handleDroppedFile(fileData)
              .then(result => {
                console.log('文件处理结果:', result);

                // 如果成功获取到路径，触发分析
                if (result.success && result.path) {
                  console.log('成功获取文件路径，准备分析:', result.path);

                  // 触发自定义事件，通知React组件
                  const event = new CustomEvent('file-path-resolved', {
                    detail: {
                      path: result.path,
                      originalPath: result.originalPath || fileData.path || fileData.name,
                      name: fileData.name,
                      success: true
                    }
                  });
                  document.dispatchEvent(event);
                } else {
                  console.warn('无法解析文件路径:', result.error);

                  // 触发错误事件
                  const event = new CustomEvent('file-path-resolved', {
                    detail: {
                      error: result.error,
                      name: fileData.name,
                      success: false
                    }
                  });
                  document.dispatchEvent(event);
                }
              })
              .catch(err => {
                console.error('处理拖放文件时出错:', err);

                // 触发错误事件
                const event = new CustomEvent('file-path-resolved', {
                  detail: {
                    error: err.message || '处理文件时出错',
                    name: fileData.name,
                    success: false
                  }
                });
                document.dispatchEvent(event);
              });
          } else {
            console.warn('handleDroppedFile API不可用');

            // 触发错误事件
            const event = new CustomEvent('file-path-resolved', {
              detail: {
                error: 'handleDroppedFile API不可用',
                name: fileData.name,
                success: false
              }
            });
            document.dispatchEvent(event);
          }
        }
      });

      // 添加自定义事件监听器，用于React组件
      if (!window._fileDropListenerAdded) {
        window._fileDropListenerAdded = true;

        document.addEventListener('file-path-resolved', (e) => {
          console.log('收到file-path-resolved事件:', e.detail);

          // 如果有React组件注册的回调函数，调用它
          if (window._fileDropCallback && typeof window._fileDropCallback === 'function') {
            window._fileDropCallback(e.detail);
          }
        });

        // 添加全局注册回调的方法
        window.registerFileDropCallback = (callback) => {
          console.log('注册文件拖放回调函数');
          window._fileDropCallback = callback;
        };
      }

      console.log('高级拖放处理脚本已安装');
    `);
  });

  // 加载应用
  const startUrl = isDev
    ? 'http://localhost:3000'  // 开发环境
    : `file://${path.join(__dirname, '../out/index.html')}`; // 生产环境

  console.log(`加载URL: ${startUrl}`);
  mainWindow.loadURL(startUrl);

  // 默认不打开开发者工具，只能通过F12打开
  // 窗口加载完成后记录日志
  mainWindow.webContents.on('did-finish-load', () => {
    console.log('窗口加载完成');
  });

  // 设置本地窗口快捷键
  mainWindow.webContents.on('before-input-event', (event, input) => {
    if (input.key === 'F12') {
      console.log('检测到F12按键');
      if (mainWindow.webContents.isDevToolsOpened()) {
        console.log('关闭开发者工具');
        mainWindow.webContents.closeDevTools();
      } else {
        console.log('打开开发者工具');
        mainWindow.webContents.openDevTools();
      }
      event.preventDefault();
    }
  });

  // 监听文件拖放事件
  mainWindow.webContents.on('will-navigate', (event, url) => {
    // 阻止默认导航行为
    event.preventDefault();
    console.log('拦截到导航事件:', url);
  });

  // 设置文件拖放处理
  mainWindow.webContents.session.on('will-download', (event, item, webContents) => {
    console.log('拦截到下载事件:', item.getFilename());
    console.log('下载路径:', item.getURL());

    // 获取文件路径并发送到渲染进程
    const filePath = item.getURL().replace('file:///', '');
    console.log('文件路径:', filePath);

    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('file-dropped', {
        path: filePath,
        name: item.getFilename()
      });
    }

    // 取消下载
    item.cancel();
  });

  // 当窗口关闭时触发
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// 启动后端服务
function startBackendServer() {
  const appRoot = isDev ? path.join(__dirname, '..', '..') : path.join(process.resourcesPath, 'app');
  const backendDir = path.join(appRoot, 'backend');
  const pythonExe = isDev
    ? path.join(appRoot, '.venv', 'Scripts', 'python.exe')
    : path.join(process.resourcesPath, 'python', 'python.exe');

  if (!fs.existsSync(backendDir)) {
    console.error(`后端目录不存在: ${backendDir}`);
    return;
  }

  if (!fs.existsSync(pythonExe)) {
    console.error(`Python可执行文件不存在: ${pythonExe}`);
    return;
  }

  console.log(`启动后端服务: ${pythonExe} main.py (在 ${backendDir})`);

  // 启动Python后端
  backendProcess = spawn(pythonExe, ['main.py'], {
    cwd: backendDir,
    stdio: 'pipe'
  });

  backendProcess.stdout.on('data', (data) => {
    console.log(`后端输出: ${data}`);
  });

  backendProcess.stderr.on('data', (data) => {
    console.error(`后端错误: ${data}`);
  });

  backendProcess.on('close', (code) => {
    console.log(`后端进程退出，代码: ${code}`);
    backendProcess = null;
  });
}

// 处理IPC消息
function setupIPC() {
  // 注册一个新的IPC处理程序，用于接收拖拽文件的请求
  ipcMain.handle('register-file-drop-handler', () => {
    console.log('注册文件拖放处理程序');

    // 设置文件拖放处理
    if (mainWindow && !mainWindow.isDestroyed()) {
      // 允许拖放文件
      mainWindow.webContents.on('will-navigate', (event, url) => {
        if (url.startsWith('file://')) {
          event.preventDefault();
          console.log('拦截到文件拖放:', url);

          // 解析文件路径
          const filePath = decodeURIComponent(url.replace('file:///', ''));
          console.log('解析后的文件路径:', filePath);

          // 发送到渲染进程
          mainWindow.webContents.send('file-dropped', {
            path: filePath,
            name: path.basename(filePath)
          });
        }
      });
    }

    return { success: true };
  });

  // 处理文件选择对话框
  ipcMain.handle('dialog:openFile', async () => {
    console.log('处理文件选择请求');

    if (!mainWindow) {
      console.error('主窗口不存在，无法打开文件对话框');
      return { canceled: true, error: '主窗口不存在' };
    }

    try {
      // 设置对话框主题 - 始终使用亮色主题，无论应用是否处于暗色模式
      const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openFile'],
        filters: [
          { name: 'USD Files', extensions: ['usd', 'usda', 'usdc'] }
        ],
        title: '选择USD文件',
        // 强制使用亮色主题
        backgroundColor: '#ffffff',
        // 在Windows上使用系统亮色主题
        customization: {
          themeOverride: 'light',
          colors: {
            background: '#ffffff',
            foreground: '#000000',
            selectionBackground: '#0078d7',
            selectionForeground: '#ffffff'
          }
        }
      });

      console.log('文件选择结果:', result);
      return result;
    } catch (error) {
      console.error('文件选择错误:', error);
      return { canceled: true, error: error.message };
    }
  });

  // 处理分析请求
  ipcMain.handle('start-analysis', () => {
    console.log('处理分析请求');
    return { success: true, message: '分析请求已处理' };
  });

  // 处理主题模式切换
  ipcMain.handle('set-theme-mode', (event, darkMode) => {
    console.log('处理主题模式切换:', darkMode ? '暗色模式' : '亮色模式');

    // 更新全局主题模式
    isDarkMode = darkMode;

    if (mainWindow && !mainWindow.isDestroyed()) {
      // 设置窗口背景色
      mainWindow.setBackgroundColor(isDarkMode ? '#1a1a1a' : '#ffffff');

      // 返回成功
      return { success: true };
    }

    return { success: false, error: '主窗口不存在' };
  });

  // 增强版拖拽文件路径处理
  ipcMain.handle('handle-dropped-file', async (event, fileData) => {
    console.log('增强版拖拽文件路径处理:', fileData);

    try {
      // 创建详细日志
      const logDetails = {
        timestamp: new Date().toISOString(),
        fileData: JSON.stringify(fileData),
        platform: process.platform,
        steps: []
      };

      // 添加日志步骤的辅助函数
      const logStep = (step, details) => {
        const logEntry = { step, details, timestamp: new Date().toISOString() };
        console.log(`[拖拽处理] ${step}:`, details);
        logDetails.steps.push(logEntry);
        return logEntry;
      };

      // 初始化文件路径变量
      let filePath = '';
      let originalPath = '';
      let fileExists = false;

      // 步骤1: 从各种可能的来源提取路径
      logStep('步骤1', '从各种可能的来源提取路径');

      // 1.1 如果提供了path属性，优先使用
      if (fileData.path) {
        originalPath = fileData.path;
        filePath = fileData.path;
        logStep('1.1', `从fileData.path获取路径: ${filePath}`);
      }
      // 1.2 如果提供了URL，解析路径
      else if (fileData.url) {
        originalPath = fileData.url;
        if (fileData.url.startsWith('file://')) {
          // 移除file://前缀，处理不同操作系统的差异
          if (process.platform === 'win32') {
            // Windows: file:///C:/path/to/file.usd
            filePath = fileData.url.replace(/^file:\/\/\//, '');
          } else {
            // macOS/Linux: file:///path/to/file.usd
            filePath = fileData.url.replace(/^file:\/\//, '');
          }

          // 处理URL编码
          filePath = decodeURIComponent(filePath);
          logStep('1.2', `从URL解析路径: ${filePath}`);
        } else {
          logStep('1.2', `URL不是file://格式: ${fileData.url}`);
        }
      }
      // 1.3 如果有webkitRelativePath属性
      else if (fileData.webkitRelativePath) {
        originalPath = fileData.webkitRelativePath;
        filePath = fileData.webkitRelativePath;
        logStep('1.3', `从webkitRelativePath获取路径: ${filePath}`);
      }
      // 1.4 如果只有文件名
      else if (fileData.name) {
        originalPath = fileData.name;
        filePath = fileData.name;
        logStep('1.4', `只有文件名: ${filePath}`);
      }

      // 步骤2: 规范化和修复路径
      logStep('步骤2', '规范化和修复路径');

      // 2.1 处理Windows路径分隔符
      if (process.platform === 'win32') {
        // 替换正斜杠为反斜杠
        const oldPath = filePath;
        filePath = filePath.replace(/\//g, '\\');
        if (oldPath !== filePath) {
          logStep('2.1', `修复Windows路径分隔符: ${oldPath} -> ${filePath}`);
        }
      }

      // 2.2 处理可能的相对路径
      if (!path.isAbsolute(filePath) && fileData.name) {
        const oldPath = filePath;
        // 如果不是绝对路径，尝试构建绝对路径
        if (process.platform === 'win32' && !filePath.match(/^[a-zA-Z]:/)) {
          // 检查是否缺少盘符
          if (filePath.startsWith('\\')) {
            // 如果以反斜杠开头，添加盘符
            filePath = `E:${filePath}`;
            logStep('2.2.1', `添加盘符: ${oldPath} -> ${filePath}`);
          } else {
            // 否则，假设它是一个相对路径，尝试在常见目录中查找
            logStep('2.2.2', `处理相对路径: ${filePath}`);
          }
        }
      }

      // 步骤3: 验证文件是否存在
      logStep('步骤3', '验证文件是否存在');

      // 3.1 检查文件是否存在
      if (filePath) {
        try {
          fileExists = fs.existsSync(filePath);
          logStep('3.1', `检查文件是否存在: ${filePath}, 结果: ${fileExists}`);
        } catch (error) {
          logStep('3.1', `检查文件存在时出错: ${error.message}`);
        }
      }

      // 步骤4: 如果文件不存在，尝试修复路径
      if (!fileExists) {
        logStep('步骤4', '尝试修复路径');

        // 4.1 尝试添加盘符
        if (process.platform === 'win32' && !filePath.match(/^[a-zA-Z]:/)) {
          const testPath = `E:${filePath}`;
          try {
            if (fs.existsSync(testPath)) {
              filePath = testPath;
              fileExists = true;
              logStep('4.1', `添加盘符后文件存在: ${filePath}`);
            } else {
              logStep('4.1', `添加盘符后文件仍不存在: ${testPath}`);
            }
          } catch (error) {
            logStep('4.1', `检查添加盘符后的路径时出错: ${error.message}`);
          }
        }

        // 4.2 尝试在常见目录中查找文件
        if (!fileExists && fileData.name) {
          const filename = fileData.name;
          // 定义常见目录列表，按优先级排序
          const commonDirs = [
            'E:\\filmserver\\test\\library\\prop\\all\\main\\lookdev\\workarea\\usd',
            'E:\\filmserver\\test\\library\\prop\\all\\main\\lookdev\\publish\\v001',
            'E:\\filmserver\\test\\library\\env\\test\\aa\\lookdev\\publish\\v001',
            'E:\\filmserver\\test\\library\\prop',
            'E:\\filmserver\\test\\library\\env',
            'E:\\filmserver\\test\\library',
            'E:\\filmserver\\test',
            'D:\\filmserver\\test',
            'C:\\filmserver\\test',
            'E:\\test',
            'D:\\test',
            'C:\\test',
            // 添加更多可能的目录
          ];

          logStep('4.2', `在常见目录中查找文件: ${filename}`);

          // 遍历常见目录
          for (const dir of commonDirs) {
            const testPath = path.join(dir, filename);
            try {
              if (fs.existsSync(testPath)) {
                filePath = testPath;
                fileExists = true;
                logStep('4.2', `在目录中找到文件: ${filePath}`);
                break;
              }
            } catch (error) {
              logStep('4.2', `检查目录时出错: ${dir}, 错误: ${error.message}`);
            }
          }
        }

        // 4.3 尝试在常见目录中查找文件（使用basename）
        if (!fileExists && filePath) {
          const basename = path.basename(filePath);
          // 定义常见目录列表，按优先级排序
          const commonDirs = [
            'E:\\filmserver\\test\\library\\prop\\all\\main\\lookdev\\workarea\\usd',
            'E:\\filmserver\\test\\library\\prop\\all\\main\\lookdev\\publish\\v001',
            'E:\\filmserver\\test\\library\\env\\test\\aa\\lookdev\\publish\\v001',
            'E:\\filmserver\\test\\library\\prop',
            'E:\\filmserver\\test\\library\\env',
            'E:\\filmserver\\test\\library',
            'E:\\filmserver\\test',
            'D:\\filmserver\\test',
            'C:\\filmserver\\test',
            'E:\\test',
            'D:\\test',
            'C:\\test',
            // 添加更多可能的目录
          ];

          logStep('4.3', `使用basename在常见目录中查找文件: ${basename}`);

          // 遍历常见目录
          for (const dir of commonDirs) {
            const testPath = path.join(dir, basename);
            try {
              if (fs.existsSync(testPath)) {
                filePath = testPath;
                fileExists = true;
                logStep('4.3', `在目录中找到文件: ${filePath}`);
                break;
              }
            } catch (error) {
              logStep('4.3', `检查目录时出错: ${dir}, 错误: ${error.message}`);
            }
          }
        }
      }

      // 步骤5: 返回结果
      logStep('步骤5', '返回结果');

      if (fileExists) {
        logStep('5.1', `成功: 文件存在于路径: ${filePath}`);
        return {
          success: true,
          path: filePath,
          originalPath: originalPath,
          log: logDetails
        };
      } else {
        logStep('5.2', `失败: 无法找到文件`);
        return {
          success: false,
          error: '无法找到文件',
          originalPath: originalPath,
          attemptedPath: filePath,
          log: logDetails
        };
      }
    } catch (error) {
      console.error('处理拖拽文件路径时出错:', error);
      return {
        success: false,
        error: `处理拖拽文件时出错: ${error.message}`,
        stack: error.stack
      };
    }
  });

  // 处理获取文件绝对路径请求
  ipcMain.handle('get-file-path', (event, relativePath) => {
    console.log('处理获取文件绝对路径请求:', relativePath);

    try {
      // 如果是相对路径，转换为绝对路径
      let absolutePath = relativePath;

      if (relativePath.startsWith('./') || relativePath.startsWith('../') || !path.isAbsolute(relativePath)) {
        // 获取当前工作目录
        const cwd = process.cwd();
        console.log('当前工作目录:', cwd);

        // 解析绝对路径
        absolutePath = path.resolve(cwd, relativePath);
        console.log('解析后的绝对路径:', absolutePath);

        // 检查文件是否存在
        if (fs.existsSync(absolutePath)) {
          console.log('文件存在:', absolutePath);
        } else {
          console.warn('文件不存在:', absolutePath);

          // 尝试在常见目录中查找文件
          const filename = path.basename(relativePath);
          const commonDirs = [
            'E:\\filmserver\\test\\library\\prop\\all\\main\\lookdev\\workarea\\usd',
            'E:\\filmserver\\test\\library\\prop\\all\\main\\lookdev\\publish\\v001',
            'E:\\filmserver\\test\\library\\env\\test\\aa\\lookdev\\publish\\v001',
            'E:\\filmserver\\test\\library\\prop',
            'E:\\filmserver\\test\\library\\env',
            'E:\\filmserver\\test\\library',
            'E:\\filmserver\\test'
          ];

          for (const dir of commonDirs) {
            const testPath = path.join(dir, filename);
            console.log('尝试路径:', testPath);

            if (fs.existsSync(testPath)) {
              absolutePath = testPath;
              console.log('找到文件:', absolutePath);
              break;
            }
          }
        }
      }

      return { success: true, path: absolutePath };
    } catch (error) {
      console.error('获取文件绝对路径错误:', error);
      return { success: false, error: error.message };
    }
  });
}

// 注册F12快捷键函数
function registerF12Shortcut() {
  console.log('注册F12快捷键');

  // 先注销所有快捷键，防止重复注册
  globalShortcut.unregisterAll();

  const registered = globalShortcut.register('F12', () => {
    console.log('F12快捷键被触发');
    const windows = BrowserWindow.getAllWindows();
    if (windows.length > 0) {
      const win = windows[0];
      if (win.webContents.isDevToolsOpened()) {
        console.log('关闭开发者工具');
        win.webContents.closeDevTools();
      } else {
        console.log('打开开发者工具');
        win.webContents.openDevTools();
      }
    }
  });

  if (!registered) {
    console.error('F12快捷键注册失败');
  } else {
    console.log('F12快捷键注册成功');
  }
}

// 应用初始化
app.whenReady().then(() => {
  console.log('Electron应用已准备就绪');

  // 设置IPC处理程序
  setupIPC();

  // 启动后端服务
  startBackendServer();

  // 创建窗口
  setTimeout(() => {
    createWindow();

    // 注册F12快捷键
    registerF12Shortcut();
  }, 1000);

  // 处理应用激活
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
      // 重新注册F12快捷键
      registerF12Shortcut();
    }
  });
});

// 当所有窗口关闭时退出应用
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    if (backendProcess) {
      backendProcess.kill();
    }
    app.quit();
  }
});

// 在应用退出前关闭后端进程并注销快捷键
app.on('before-quit', () => {
  // 注销所有快捷键
  globalShortcut.unregisterAll();

  // 关闭后端进程
  if (backendProcess) {
    backendProcess.kill();
  }
});
