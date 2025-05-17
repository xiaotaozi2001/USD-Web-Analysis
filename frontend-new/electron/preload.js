// 预加载脚本 - 增强版
const { contextBridge, ipcRenderer } = require('electron');
const path = require('path');
const fs = require('fs');

// 创建一个回调函数存储对象
const fileDropCallbacks = [];
const filePathResolvedCallbacks = [];

// 监听来自主进程的文件拖放事件
ipcRenderer.on('file-dropped', (event, fileInfo) => {
  console.log('收到文件拖放事件:', fileInfo);

  // 调用所有注册的回调函数
  fileDropCallbacks.forEach(callback => {
    try {
      callback(fileInfo);
    } catch (error) {
      console.error('执行文件拖放回调时出错:', error);
    }
  });

  // 如果有路径信息，尝试处理它
  if (fileInfo && fileInfo.path) {
    // 使用增强版API处理文件路径
    ipcRenderer.invoke('handle-dropped-file', fileInfo)
      .then(result => {
        console.log('预加载脚本处理拖放文件结果:', result);

        // 通知所有注册的路径解析回调
        filePathResolvedCallbacks.forEach(callback => {
          try {
            callback({
              success: result.success,
              path: result.path,
              originalPath: result.originalPath || fileInfo.path,
              name: fileInfo.name,
              error: result.error,
              source: 'preload-script'
            });
          } catch (error) {
            console.error('执行路径解析回调时出错:', error);
          }
        });
      })
      .catch(error => {
        console.error('预加载脚本处理拖放文件错误:', error);

        // 通知所有注册的路径解析回调
        filePathResolvedCallbacks.forEach(callback => {
          try {
            callback({
              success: false,
              error: error.message || '处理文件路径时出错',
              name: fileInfo.name,
              source: 'preload-script-error'
            });
          } catch (callbackError) {
            console.error('执行路径解析回调时出错:', callbackError);
          }
        });
      });
  }
});

// 直接暴露IPC通信方法
contextBridge.exposeInMainWorld('electron', {
  // 文件操作
  openFile: () => ipcRenderer.invoke('dialog:openFile'),

  // 获取文件绝对路径
  getFilePath: (relativePath) => ipcRenderer.invoke('get-file-path', relativePath),

  // 设置主题模式
  setThemeMode: (isDarkMode) => ipcRenderer.invoke('set-theme-mode', isDarkMode),

  // 增强版拖拽文件处理 - 直接调用主进程API
  handleDroppedFile: (fileData) => ipcRenderer.invoke('handle-dropped-file', fileData),

  // 监听文件拖拽事件 - 基础版
  onFileDropped: (callback) => {
    if (typeof callback === 'function') {
      fileDropCallbacks.push(callback);
    }
    return () => {
      const index = fileDropCallbacks.indexOf(callback);
      if (index !== -1) {
        fileDropCallbacks.splice(index, 1);
      }
    };
  },

  // 监听文件路径解析事件 - 增强版
  onFilePathResolved: (callback) => {
    console.log('注册文件路径解析回调');
    if (typeof callback === 'function') {
      filePathResolvedCallbacks.push(callback);

      // 在DOM加载完成后，注册浏览器端的回调
      if (typeof window !== 'undefined' && typeof document !== 'undefined') {
        setTimeout(() => {
          if (window.registerFileDropCallback) {
            window.registerFileDropCallback((data) => {
              console.log('浏览器端文件拖放回调被触发:', data);
              callback(data);
            });
          }
        }, 1000);
      }
    }

    return () => {
      const index = filePathResolvedCallbacks.indexOf(callback);
      if (index !== -1) {
        filePathResolvedCallbacks.splice(index, 1);
      }
    };
  },

  // 注册文件拖放处理程序 - 向主进程注册
  registerFileDropHandler: (callback) => {
    console.log('注册文件拖放处理程序');

    // 注册回调函数
    if (typeof callback === 'function') {
      fileDropCallbacks.push(callback);
    }

    // 通知主进程注册文件拖放处理程序
    return ipcRenderer.invoke('register-file-drop-handler');
  },

  // 分析操作
  startAnalysis: () => ipcRenderer.invoke('start-analysis'),

  // 版本信息
  versions: {
    node: () => process.versions.node,
    chrome: () => process.versions.chrome,
    electron: () => process.versions.electron
  },

  // 增强版文件拖拽处理 - 完整流程
  processDroppedFile: async (fileData) => {
    console.log('处理拖拽文件 (完整流程):', fileData);

    if (!fileData) {
      return { success: false, error: '没有文件数据' };
    }

    try {
      // 1. 收集所有可能的路径信息
      const enhancedFileData = { ...fileData };

      // 2. 调用主进程处理文件路径
      const result = await ipcRenderer.invoke('handle-dropped-file', enhancedFileData);
      console.log('主进程处理结果:', result);

      // 3. 通知所有注册的回调
      if (result.success) {
        filePathResolvedCallbacks.forEach(callback => {
          try {
            callback({
              success: true,
              path: result.path,
              originalPath: result.originalPath || enhancedFileData.path || enhancedFileData.name,
              name: enhancedFileData.name,
              source: 'process-dropped-file'
            });
          } catch (error) {
            console.error('执行路径解析回调时出错:', error);
          }
        });
      } else {
        filePathResolvedCallbacks.forEach(callback => {
          try {
            callback({
              success: false,
              error: result.error,
              name: enhancedFileData.name,
              source: 'process-dropped-file-error'
            });
          } catch (error) {
            console.error('执行路径解析回调时出错:', error);
          }
        });
      }

      return result;
    } catch (error) {
      console.error('处理拖拽文件错误:', error);

      // 通知所有注册的回调
      filePathResolvedCallbacks.forEach(callback => {
        try {
          callback({
            success: false,
            error: error.message || '处理文件时出错',
            name: fileData.name,
            source: 'process-dropped-file-exception'
          });
        } catch (callbackError) {
          console.error('执行路径解析回调时出错:', callbackError);
        }
      });

      return {
        success: false,
        error: error.message || '处理文件时出错',
        stack: error.stack
      };
    }
  },

  // 测试方法
  ping: () => 'pong'
});

// 在DOM加载完成后执行
window.addEventListener('DOMContentLoaded', () => {
  console.log('Electron预加载脚本已加载');
  // 不再添加调试标记和调试面板
});
