'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useDropzone } from 'react-dropzone';

// 扩展Window接口，添加Electron API
declare global {
  interface Window {
    electron?: {
      // 基础文件操作
      openFile: () => Promise<any>;
      getFilePath: (relativePath: string) => Promise<any>;

      // 拖拽文件处理 - 增强版API
      handleDroppedFile: (fileData: any) => Promise<any>;
      processDroppedFile: (fileData: any) => Promise<any>;

      // 事件监听
      onFileDropped: (callback: (fileData: any) => void) => (() => void);
      onFilePathResolved: (callback: (fileData: any) => void) => (() => void);
      registerFileDropHandler: (callback: (fileInfo: any) => void) => void;

      // 其他功能
      setThemeMode: (isDarkMode: boolean) => Promise<any>;
      startAnalysis: () => Promise<any>;
      versions: {
        node: () => string;
        chrome: () => string;
        electron: () => string;
      };
      ping: () => string;
    };
    electronAPI?: any;
    electronAPIExposed?: boolean;
    registerFileDropCallback?: (callback: (data: any) => void) => void;
    _fileDropCallback?: (data: any) => void;
    _fileDropListenerAdded?: boolean;
  }
}

interface Reference {
  path: string;
  type: string;
  prim_path: string;
}

interface Texture {
  path: string;
  source: string;  // 修改为 source 而不是 shader
  exists?: boolean;
  type?: string;
  udim_count?: number;
  actual_texture_count?: number;
}

interface AnalysisResult {
  filename: string;
  timestamp?: string; // 添加时间戳字段
  analysis: {
    success: boolean;
    references: Reference[];
    textures: Texture[];
    error?: string;
    texture_udim_counts?: Record<string, number>;
  };
}

interface FileItem {
  name: string;
  path: string;
  is_directory: boolean;
  size: number | null;
}

interface DirectoryContent {
  current_path: string;
  parent_path: string | null;
  items: FileItem[];
}

export default function Home() {
  const [results, setResults] = useState<AnalysisResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filePath, setFilePath] = useState<string>('');
  const [selectedResult, setSelectedResult] = useState<AnalysisResult | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});
  const [showReferences, setShowReferences] = useState(false);
  const [showTextures, setShowTextures] = useState(false);
  const [darkMode, setDarkMode] = useState(false); // 默认为日间模式（亮色）
  const [showFileBrowser, setShowFileBrowser] = useState(false);
  const [directoryContent, setDirectoryContent] = useState<DirectoryContent | null>(null);
  const [outputPath, setOutputPath] = useState<string>('');
  const [isPackaging, setIsPackaging] = useState(false);
  const [packageResult, setPackageResult] = useState<{success: boolean; message: string} | null>(null);
  const [isLoadingDirectory, setIsLoadingDirectory] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filteredItems, setFilteredItems] = useState<FileItem[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 增强版拖拽区域处理函数
  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    console.log('接收到拖放文件:', acceptedFiles);

    // 检查是否有文件
    if (!acceptedFiles || acceptedFiles.length === 0) {
      setError('未接收到任何文件');
      return;
    }

    // 过滤有效的USD文件
    const validFiles = acceptedFiles.filter(file => {
      const extension = file.name.split('.').pop()?.toLowerCase();
      return extension === 'usd' || extension === 'usda' || extension === 'usdc';
    });

    if (validFiles.length === 0) {
      setError('请上传 .usd, .usda 或 .usdc 文件');
      return;
    }

    // 获取第一个有效文件
    const file = validFiles[0];

    setIsLoading(true);
    setError(null);

    try {
      console.log('处理拖拽文件:', file.name, '文件大小:', file.size, 'bytes');

      // 检查是否在Electron环境中
      const isElectronEnv = typeof window !== 'undefined' &&
        (window.electron || window.electronAPI ||
        (navigator.userAgent && navigator.userAgent.indexOf('Electron') >= 0));

      // 在Electron环境中，使用增强版API处理文件
      if (isElectronEnv && window.electron) {
        // 收集所有可能的路径信息
        const fileData: any = {
          name: file.name,
          size: file.size,
          type: file.type,
          lastModified: file.lastModified,
          source: 'react-dropzone'
        };

        // 尝试获取路径信息
        if ('path' in file) {
          // @ts-ignore - 非标准属性
          fileData.path = file.path;
        }

        if ('webkitRelativePath' in file && file.webkitRelativePath) {
          fileData.webkitRelativePath = file.webkitRelativePath;
        }

        console.log('使用增强版API处理拖拽文件:', fileData);

        // 使用processDroppedFile API处理文件
        if (window.electron.processDroppedFile) {
          try {
            const result = await window.electron.processDroppedFile(fileData);
            console.log('processDroppedFile结果:', result);

            // 如果成功获取到路径，直接处理
            if (result.success && result.path) {
              await handleResolvedPath(result.path, file.name);
              return;
            } else {
              console.warn('无法解析文件路径:', result.error);
              // 继续使用文件上传方式
            }
          } catch (error) {
            console.error('使用processDroppedFile处理文件时出错:', error);
            // 继续使用文件上传方式
          }
        } else {
          // 回退到旧版API
          try {
            if (window.electron.handleDroppedFile) {
              const result = await window.electron.handleDroppedFile(fileData);
              console.log('handleDroppedFile结果:', result);

              if (result.success && result.path) {
                await handleResolvedPath(result.path, file.name);
                return;
              }
            }
          } catch (error) {
            console.error('使用handleDroppedFile处理文件时出错:', error);
          }
        }
      }

      // 如果不在Electron环境中或无法获取真实路径，则使用文件上传方式
      console.log('使用文件上传方式处理拖拽文件');
      await handleFileUpload(file);
    } catch (error: any) {
      console.error('分析错误:', error);
      setError(error.response?.data?.detail || error.message || '分析过程中出现错误');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 处理已解析的文件路径
  const handleResolvedPath = async (filePath: string, fileName: string) => {
    console.log('处理已解析的文件路径:', filePath);

    try {
      // 更新文件路径输入框，显示完整路径
      setFilePath(filePath);

      // 保存当前文件路径到localStorage
      localStorage.setItem('lastUsdFilePath', filePath);

      // 创建FormData对象，包含文件路径
      const formData = new FormData();
      formData.append('file_path', filePath);

      console.log('发送文件路径分析请求，路径:', filePath);

      // 添加错误处理和重试逻辑
      let response;
      let retryCount = 0;
      const maxRetries = 3;

      while (retryCount < maxRetries) {
        try {
          // 使用文件路径分析API端点
          response = await axios.post('http://localhost:63080/analyze_path', formData, {
            headers: {
              'Content-Type': 'multipart/form-data',
            },
            timeout: 30000, // 增加超时时间到30秒
          });

          // 如果请求成功，跳出循环
          break;
        } catch (err: any) {
          retryCount++;
          console.warn(`分析请求失败，尝试重试 ${retryCount}/${maxRetries}:`, err.message);

          if (retryCount >= maxRetries) {
            throw err; // 重试次数用完，抛出错误
          }

          // 等待一段时间再重试
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
      }

      if (!response) {
        throw new Error('分析请求失败，请检查后端服务是否正常运行');
      }

      console.log('收到分析响应:', response.data);

      // 检查响应是否包含错误
      if (response.data.analysis && response.data.analysis.success === false) {
        const errorMessage = response.data.analysis.error || '分析失败，未知错误';
        console.error('分析失败:', errorMessage);
        setError(errorMessage);
        return;
      }

      // 添加时间戳到结果对象
      const resultWithTimestamp = {
        ...response.data,
        timestamp: new Date().toLocaleString()
      };

      // 将新结果添加到列表开头
      setResults(prevResults => [resultWithTimestamp, ...prevResults]);
      // 自动选择新结果
      setSelectedResult(resultWithTimestamp);
      // 默认展开引用列表，隐藏纹理列表
      setShowReferences(true);
      setShowTextures(false);
    } catch (error: any) {
      console.error('分析路径时出错:', error);
      setError(error.response?.data?.detail || error.message || '分析过程中出现错误');
      throw error; // 重新抛出错误，让调用者处理
    }
  };

  // 处理文件上传 - 修改为使用analyze_path接口
  const handleFileUpload = async (file: File) => {
    console.log('处理文件上传:', file.name);

    try {
      // 首先尝试获取文件的原始路径
      let originalPath = '';

      // 尝试从file对象获取路径信息
      if ('path' in file) {
        // @ts-ignore - 非标准属性
        originalPath = file.path;
        console.log('从file对象获取到原始路径:', originalPath);

        // 如果获取到了原始路径，直接使用analyze_path接口
        if (originalPath) {
          console.log('使用原始路径和analyze_path接口');
          return await handleResolvedPath(originalPath, file.name);
        }
      }

      // 如果无法获取原始路径，则使用文件上传方式
      console.log('无法获取原始路径，使用文件上传方式');

      // 创建FormData对象，包含文件
      const formData = new FormData();
      formData.append('file', file);

      // 添加一个标志，告诉后端这是拖拽的文件
      formData.append('is_drag_drop', 'true');

      console.log('发送文件上传请求');

      // 使用文件上传API端点
      const response = await axios.post('http://localhost:63080/analyze', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 30000, // 增加超时时间到30秒
      });

      console.log('收到分析响应:', response.data);

      // 检查响应是否包含错误
      if (response.data.analysis && response.data.analysis.success === false) {
        const errorMessage = response.data.analysis.error || '分析失败，未知错误';
        console.error('分析失败:', errorMessage);
        setError(errorMessage);
        return;
      }

      // 如果后端返回了原始路径，更新文件路径输入框
      if (response.data.original_path) {
        console.log('后端返回的原始路径:', response.data.original_path);
        setFilePath(response.data.original_path);

        // 保存到localStorage
        localStorage.setItem('lastUsdFilePath', response.data.original_path);
      } else {
        // 否则只显示文件名
        setFilePath(file.name);

        // 保存到localStorage
        localStorage.setItem('lastUsdFilePath', file.name);
      }

      // 添加时间戳到结果对象
      const resultWithTimestamp = {
        ...response.data,
        timestamp: new Date().toLocaleString()
      };

      // 将新结果添加到列表开头
      setResults(prevResults => [resultWithTimestamp, ...prevResults]);
      // 自动选择新结果
      setSelectedResult(resultWithTimestamp);
      // 默认展开引用列表，隐藏纹理列表
      setShowReferences(true);
      setShowTextures(false);
    } catch (error: any) {
      console.error('上传文件时出错:', error);
      setError(error.response?.data?.detail || error.message || '分析过程中出现错误');
      throw error; // 重新抛出错误，让调用者处理
    }
  };

  // 设置拖拽区域
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/octet-stream': ['.usd', '.usda', '.usdc'],
      'text/plain': ['.usda']
    },
    multiple: false,
    noClick: false,
    noKeyboard: false,
    preventDropOnDocument: true,
    useFsAccessApi: false // 禁用File System Access API，使用传统方法
  });

  // 加载目录内容
  const loadDirectory = async (path: string = "") => {
    setIsLoadingDirectory(true);
    setError(null);
    setSearchTerm('');

    try {
      const response = await axios.get(`http://localhost:63080/browse_directory`, {
        params: { directory_path: path }
      });

      setDirectoryContent(response.data);
      setFilteredItems(response.data.items);
    } catch (error: any) {
      console.error('加载目录错误:', error);
      setError(error.response?.data?.detail || error.message || '加载目录失败');
    } finally {
      setIsLoadingDirectory(false);
    }
  };

  // 初始化主题
  useEffect(() => {
    // 初始化body样式
    if (typeof document !== 'undefined') {
      document.body.style.backgroundColor = darkMode ? '#1a1a1a' : '#ffffff';
      document.body.style.color = darkMode ? '#e0e0e0' : '#333';
      document.body.style.margin = '0';
      document.body.style.padding = '0';
      document.body.style.transition = 'all 0.3s ease';
      document.body.style.minHeight = '100vh';
    }

    // 通知Electron主进程设置窗口背景色
    if (typeof window !== 'undefined' && window.electron && window.electron.setThemeMode) {
      window.electron.setThemeMode(darkMode);
    }
  }, [darkMode]);

  // 在组件加载时初始化文件浏览器和恢复上一次的文件路径
  useEffect(() => {
    // 如果文件浏览器显示，则加载目录内容
    if (showFileBrowser) {
      loadDirectory();
    }

    // 恢复上一次的文件路径
    const lastPath = localStorage.getItem('lastUsdFilePath');
    if (lastPath) {
      setFilePath(lastPath);
    }

    // 注册文件拖放处理程序
    const isElectronEnv = typeof window !== 'undefined' &&
      (window.electron || window.electronAPI ||
      (navigator.userAgent && navigator.userAgent.indexOf('Electron') >= 0));

    if (isElectronEnv && window.electron && window.electron.registerFileDropHandler) {
      console.log('注册文件拖放处理程序');

      window.electron.registerFileDropHandler(async (fileInfo) => {
        console.log('收到文件拖放事件:', fileInfo);

        if (fileInfo && fileInfo.path) {
          const filePath = fileInfo.path;
          console.log('拖放文件路径:', filePath);

          // 检查文件扩展名
          const extension = filePath.split('.').pop()?.toLowerCase();
          if (extension !== 'usd' && extension !== 'usda' && extension !== 'usdc') {
            setError('请选择有效的USD文件 (.usd, .usda, .usdc)');
            return;
          }

          setIsLoading(true);
          setError(null);

          try {
            // 更新文件路径输入框，显示完整路径
            setFilePath(filePath);

            // 保存当前文件路径到localStorage
            localStorage.setItem('lastUsdFilePath', filePath);

            // 使用handleResolvedPath处理文件路径
            const fileName = filePath.split(/[\/\\]/).pop() || '';
            await handleResolvedPath(filePath, fileName);
          } catch (error: any) {
            console.error('分析错误:', error);
            setError(error.response?.data?.detail || error.message || '分析过程中出现错误');
          } finally {
            setIsLoading(false);
          }
        }
      });
    }
  }, [showFileBrowser]);

  // 监听文件拖拽事件
  useEffect(() => {
    // 检查是否在Electron环境中
    const isElectronEnv = typeof window !== 'undefined' &&
      (window.electron || window.electronAPI ||
      (navigator.userAgent && navigator.userAgent.indexOf('Electron') >= 0));

    if (isElectronEnv && window.electron && window.electron.onFileDropped) {
      console.log('注册文件拖拽事件监听器');

      const unsubscribe = window.electron.onFileDropped(async (fileData) => {
        console.log('收到文件拖拽事件:', fileData);

        if (fileData && fileData.path) {
          const filePath = fileData.path;
          console.log('拖拽文件路径:', filePath);

          // 检查文件扩展名
          const extension = filePath.split('.').pop()?.toLowerCase();
          if (extension !== 'usd' && extension !== 'usda' && extension !== 'usdc') {
            setError('请选择有效的USD文件 (.usd, .usda, .usdc)');
            return;
          }

          setIsLoading(true);
          setError(null);

          try {
            // 更新文件路径输入框，显示完整路径
            setFilePath(filePath);

            // 保存当前文件路径到localStorage
            localStorage.setItem('lastUsdFilePath', filePath);

            // 使用handleResolvedPath处理文件路径
            const fileName = filePath.split(/[\/\\]/).pop() || '';
            await handleResolvedPath(filePath, fileName);
          } catch (error: any) {
            console.error('分析错误:', error);
            setError(error.response?.data?.detail || error.message || '分析过程中出现错误');
          } finally {
            setIsLoading(false);
          }
        }
      });

      // 清理函数
      return () => {
        if (typeof unsubscribe === 'function') {
          unsubscribe();
        }
      };
    }
  }, []);

  // 监听文件路径解析事件 - 增强版
  useEffect(() => {
    // 检查是否在Electron环境中
    const isElectronEnv = typeof window !== 'undefined' &&
      (window.electron || window.electronAPI ||
      (navigator.userAgent && navigator.userAgent.indexOf('Electron') >= 0));

    if (isElectronEnv && window.electron && window.electron.onFilePathResolved) {
      console.log('注册文件路径解析事件监听器');

      const unsubscribe = window.electron.onFilePathResolved(async (data) => {
        console.log('收到文件路径解析事件:', data);

        if (data.success && data.path) {
          setIsLoading(true);
          setError(null);

          try {
            console.log('使用解析后的文件路径:', data.path);
            console.log('文件名:', data.name || path.basename(data.path));

            // 检查文件扩展名
            const extension = data.path.split('.').pop()?.toLowerCase();
            if (extension !== 'usd' && extension !== 'usda' && extension !== 'usdc') {
              setError('请选择有效的USD文件 (.usd, .usda, .usdc)');
              setIsLoading(false);
              return;
            }

            await handleResolvedPath(data.path, data.name || path.basename(data.path));
          } catch (error: any) {
            console.error('处理解析路径时出错:', error);
            setError(error.response?.data?.detail || error.message || '分析过程中出现错误');
          } finally {
            setIsLoading(false);
          }
        } else if (data.error) {
          setError(`文件路径解析失败: ${data.error}`);
        }
      });

      // 清理函数
      return () => {
        if (typeof unsubscribe === 'function') {
          unsubscribe();
        }
      };
    }
  }, []);

  // 检查Electron API是否可用
  useEffect(() => {
    if (typeof window !== 'undefined') {
      console.log('检查Electron API是否可用:', window.electronAPI ? '可用' : '不可用');
      console.log('检查electronAPIExposed:', window.electronAPIExposed ? '可用' : '不可用');

      if (window.electronAPI) {
        console.log('Electron API可用，获取版本信息');
        try {
          if (window.electronAPI.getVersionInfo) {
            const versionInfo = window.electronAPI.getVersionInfo();
            console.log('Electron版本信息:', versionInfo);
          } else {
            console.log('getVersionInfo方法不可用');
          }
        } catch (error) {
          console.error('获取Electron版本信息失败:', error);
        }
      } else {
        console.log('Electron API不可用，将在Web模式下运行');
      }
    }
  }, []);

  // 处理搜索
  useEffect(() => {
    if (!directoryContent) return;

    if (!searchTerm.trim()) {
      setFilteredItems(directoryContent.items);
      return;
    }

    const lowerSearchTerm = searchTerm.toLowerCase();
    const filtered = directoryContent.items.filter(item =>
      item.name.toLowerCase().includes(lowerSearchTerm)
    );

    setFilteredItems(filtered);
  }, [searchTerm, directoryContent]);

  // 选择文件
  const selectFile = (file: FileItem) => {
    if (file.is_directory) {
      loadDirectory(file.path);
    } else {
      setFilePath(file.path);
      setShowFileBrowser(false);
    }
  };

  // 返回上级目录
  const goToParentDirectory = () => {
    if (directoryContent?.parent_path) {
      loadDirectory(directoryContent.parent_path);
    }
  };

  // 处理文件选择按钮点击
  const handleFileSelect = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];

    // 获取文件路径
    // 注意：由于浏览器安全限制，这里只能获取文件名，不能获取完整路径
    // 我们需要使用特殊技巧来获取完整路径

    // 方法1：尝试使用非标准属性（仅在某些浏览器中有效）
    let path = '';
    if ('webkitRelativePath' in file && file.webkitRelativePath) {
      path = file.webkitRelativePath;
    } else if ('path' in file) {
      // @ts-ignore - 非标准属性
      path = file.path;
    } else {
      // 退回到仅使用文件名
      path = file.name;
    }

    setFilePath(path);
  };

  const openFileBrowser = async () => {
    console.log('openFileBrowser 函数被调用');

    // 检查是否在Electron环境中 - 优先使用新API
    if (typeof window !== 'undefined' && window.electron) {
      console.log('在Electron环境中，使用新的Electron API');

      try {
        // 使用新的Electron API
        console.log('调用window.electron.openFile()');
        const result = await window.electron.openFile();
        console.log('Electron文件选择结果:', result);

        if (result && !result.canceled && result.filePaths && result.filePaths.length > 0) {
          const filePath = result.filePaths[0];
          console.log('通过Electron选择的文件:', filePath);
          setFilePath(filePath);
        } else {
          console.log('用户取消了文件选择或结果无效:', result);
        }
      } catch (electronError: any) {
        console.error('Electron文件选择错误:', electronError);

        // 如果新API失败，尝试旧API
        if (window.electronAPI) {
          try {
            console.log('尝试使用旧的Electron API');
            const result = await window.electronAPI.selectFile();

            if (result && !result.canceled && result.filePaths && result.filePaths.length > 0) {
              const filePath = result.filePaths[0];
              console.log('通过旧API选择的文件:', filePath);
              setFilePath(filePath);
              return;
            }
          } catch (oldApiError) {
            console.error('旧API也失败了:', oldApiError);
          }
        }

        // 如果Electron对话框失败，回退到Web版本
        console.log('回退到Web文件浏览器');
        setShowFileBrowser(true);
        await loadDirectory();
      }
    } else if (typeof window !== 'undefined' && window.electronAPI) {
      // 尝试使用旧的API
      console.log('在Electron环境中，使用旧的Electron API');

      try {
        const result = await window.electronAPI.selectFile();
        console.log('旧API文件选择结果:', result);

        if (result && !result.canceled && result.filePaths && result.filePaths.length > 0) {
          const filePath = result.filePaths[0];
          console.log('通过旧API选择的文件:', filePath);
          setFilePath(filePath);
        } else {
          console.log('用户取消了文件选择或结果无效:', result);
        }
      } catch (error) {
        console.error('旧API错误:', error);

        // 回退到Web版本
        console.log('回退到Web文件浏览器');
        setShowFileBrowser(true);
        await loadDirectory();
      }
    } else {
      console.log('在Web环境中，使用Web文件浏览器');
      // 在Web环境中使用自定义文件浏览器
      setShowFileBrowser(true);
      await loadDirectory();
    }
  };

  const startAnalysis = async () => {
    if (!filePath.trim()) {
      setError('请选择或输入文件路径');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // 从文件路径中提取文件名
      const fileName = filePath.split(/[\/\\]/).pop() || '';

      // 检查文件扩展名
      if (!/\.(usd|usda|usdc)$/i.test(fileName)) {
        setError('文件必须是 .usd, .usda 或 .usdc 格式');
        setIsLoading(false);
        return;
      }

      // 保存当前文件路径到localStorage
      const cleanPath = filePath.trim();
      localStorage.setItem('lastUsdFilePath', cleanPath);

      // 如果在Electron环境中，尝试通过Electron API触发分析
      if (typeof window !== 'undefined') {
        // 优先使用新API
        if (window.electron) {
          try {
            console.log('尝试通过新Electron API触发分析');

            // 直接调用新Electron API
            const result = await window.electron.startAnalysis();
            console.log('新API分析结果:', result);

            if (result && result.success) {
              console.log('新API分析成功');
            } else {
              console.warn('新API分析未成功:', result);
            }
          } catch (newApiError) {
            console.error('通过新API触发分析失败:', newApiError);

            // 如果新API失败，尝试旧API
            if (window.electronAPI) {
              try {
                console.log('尝试通过旧Electron API触发分析');
                const result = await window.electronAPI.startAnalysis();
                console.log('旧API分析结果:', result);
              } catch (oldApiError) {
                console.error('通过旧API触发分析也失败:', oldApiError);
              }
            }
          }
        } else if (window.electronAPI) {
          // 使用旧API
          try {
            console.log('尝试通过旧Electron API触发分析');

            // 直接调用旧Electron API
            const result = await window.electronAPI.startAnalysis();
            console.log('旧API分析结果:', result);

            if (result && result.success) {
              console.log('旧API分析成功');
            } else {
              console.warn('旧API分析未成功:', result);
            }
          } catch (electronError) {
            console.error('通过旧API触发分析失败:', electronError);
          }
        }
      }

      // 使用handleResolvedPath处理文件路径
      await handleResolvedPath(cleanPath, fileName);
    } catch (error: any) {
      console.error('分析错误:', error);
      setError(error.response?.data?.detail || error.message || '分析过程中出现错误');
    } finally {
      setIsLoading(false);
    }
  };

  // 一键打包功能
  const packageFiles = async () => {
    if (!selectedResult) {
      setError('请先分析USD文件');
      return;
    }

    if (!outputPath) {
      setError('请输入输出路径');
      return;
    }

    try {
      setIsPackaging(true);
      setPackageResult(null);

      // 使用完整的文件路径而不是仅文件名
      // 从 localStorage 中获取之前分析的文件路径
      const savedFilePath = localStorage.getItem('lastUsdFilePath') || '';

      // 如果没有保存的路径，则使用当前输入框中的路径
      const fullFilePath = savedFilePath || filePath.trim();

      console.log('准备发送打包请求:', {
        file_path: fullFilePath,
        output_path: outputPath,
        saved_path: savedFilePath
      });

      // 使用FormData发送请求，与分析请求保持一致
      const formData = new FormData();
      formData.append('file_path', fullFilePath);
      formData.append('output_path', outputPath);

      const response = await axios.post('http://localhost:63080/package', {
        file_path: fullFilePath,
        output_path: outputPath,
        textures: selectedResult.analysis.textures,
        references: selectedResult.analysis.references
      });

      setPackageResult({
        success: response.data.success,
        message: response.data.message
      });
    } catch (error) {
      console.error('打包错误:', error);
      setPackageResult({
        success: false,
        message: '打包过程中发生错误'
      });
    } finally {
      setIsPackaging(false);
    }
  };

  // 文件浏览器组件
  const FileBrowser = () => {
    if (!showFileBrowser) return null;

    return (
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        zIndex: 1000,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center'
      }}>
        <div style={{
          width: '80%',
          height: '80%',
          backgroundColor: '#1e293b',
          borderRadius: '8px',
          padding: '20px',
          display: 'flex',
          flexDirection: 'column'
        }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginBottom: '20px'
          }}>
            <h2 style={{ margin: 0 }}>选择USD文件</h2>
            <button
              onClick={() => setShowFileBrowser(false)}
              style={{
                background: 'none',
                border: 'none',
                color: 'white',
                fontSize: '24px',
                cursor: 'pointer'
              }}
            >
              ×
            </button>
          </div>

          <div style={{
            padding: '10px',
            backgroundColor: 'rgba(255, 255, 255, 0.05)',
            borderRadius: '4px',
            marginBottom: '10px',
            display: 'flex',
            alignItems: 'center'
          }}>
            <span style={{ marginRight: '10px' }}>当前路径:</span>
            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {directoryContent?.current_path || '根目录'}
            </span>
            {directoryContent?.parent_path && (
              <button
                onClick={goToParentDirectory}
                style={{
                  backgroundColor: '#4b5563',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '5px 10px',
                  cursor: 'pointer',
                  marginLeft: '10px'
                }}
              >
                返回上级
              </button>
            )}
          </div>

          {/* 搜索框 */}
          <div style={{
            marginBottom: '10px',
            display: 'flex',
            alignItems: 'center'
          }}>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="搜索文件或目录..."
              style={{
                flex: 1,
                padding: '8px',
                borderRadius: '4px',
                border: '1px solid rgba(255, 255, 255, 0.2)',
                background: 'rgba(255, 255, 255, 0.05)',
                color: 'white'
              }}
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm('')}
                style={{
                  backgroundColor: '#4b5563',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '5px 10px',
                  cursor: 'pointer',
                  marginLeft: '10px'
                }}
              >
                清除
              </button>
            )}
          </div>

          <div style={{
            flex: 1,
            overflow: 'auto',
            backgroundColor: 'rgba(255, 255, 255, 0.03)',
            borderRadius: '4px',
            padding: '10px'
          }}>
            {isLoadingDirectory ? (
              <div style={{ textAlign: 'center', padding: '20px' }}>
                <div style={{
                  border: '3px solid rgba(255, 255, 255, 0.1)',
                  borderTop: '3px solid #3b82f6',
                  borderRadius: '50%',
                  width: '30px',
                  height: '30px',
                  animation: 'spin 1s linear infinite',
                  margin: '0 auto 15px'
                }}></div>
                <p>加载中...</p>
              </div>
            ) : (
              <div>
                {filteredItems.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '20px', color: '#9ca3af' }}>
                    {searchTerm ? '没有找到匹配的文件或目录' : '此目录为空'}
                  </div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '10px' }}>
                    {filteredItems.map((item, index) => (
                      <div
                        key={`${item.path}-${index}`}
                        onClick={() => selectFile(item)}
                        style={{
                          padding: '10px',
                          backgroundColor: 'rgba(255, 255, 255, 0.05)',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          transition: 'transform 0.2s ease',
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          textAlign: 'center'
                        }}
                        onMouseEnter={e => {
                          e.currentTarget.style.transform = 'translateY(-2px)';
                          e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.1)';
                        }}
                        onMouseLeave={e => {
                          e.currentTarget.style.transform = 'translateY(0)';
                          e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.05)';
                        }}
                      >
                        <div style={{
                          fontSize: '32px',
                          marginBottom: '10px',
                          color: item.is_directory ? '#3b82f6' : '#f59e0b'
                        }}>
                          {item.is_directory ? '📁' : '📄'}
                        </div>
                        <div style={{
                          fontSize: '14px',
                          wordBreak: 'break-word',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          width: '100%'
                        }}>
                          {item.name}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  // 切换日间/夜间模式
  const toggleDarkMode = () => {
    setDarkMode(prevMode => {
      const newMode = !prevMode;

      // 通知Electron主进程更新窗口背景色
      if (typeof window !== 'undefined' && window.electron && window.electron.setThemeMode) {
        window.electron.setThemeMode(newMode)
          .then(result => {
            console.log('主题模式切换结果:', result);
          })
          .catch(error => {
            console.error('主题模式切换错误:', error);
          });
      }

      // 更新body背景色，确保整个页面都应用主题
      if (typeof document !== 'undefined') {
        document.body.style.backgroundColor = newMode ? '#1a1a1a' : '#ffffff';
        document.body.style.color = newMode ? '#e0e0e0' : '#333';
        document.body.style.transition = 'all 0.3s ease';
      }

      return newMode;
    });
  };

  // 添加一个直接调用Electron API的函数
  const testElectronAPI = async () => {
    console.log('测试Electron API');

    // 创建调试面板
    const debugPanel = document.createElement('div');
    debugPanel.style.position = 'fixed';
    debugPanel.style.top = '50%';
    debugPanel.style.left = '50%';
    debugPanel.style.transform = 'translate(-50%, -50%)';
    debugPanel.style.backgroundColor = 'rgba(0, 0, 0, 0.9)';
    debugPanel.style.color = 'white';
    debugPanel.style.padding = '20px';
    debugPanel.style.borderRadius = '8px';
    debugPanel.style.zIndex = '10000';
    debugPanel.style.minWidth = '400px';
    debugPanel.style.maxWidth = '80%';
    debugPanel.style.maxHeight = '80%';
    debugPanel.style.overflow = 'auto';
    debugPanel.style.boxShadow = '0 0 20px rgba(0, 0, 0, 0.5)';
    debugPanel.style.fontFamily = 'monospace';
    debugPanel.style.fontSize = '14px';

    // 添加标题
    const title = document.createElement('h3');
    title.textContent = 'Electron API 调试面板';
    title.style.marginTop = '0';
    title.style.marginBottom = '15px';
    title.style.borderBottom = '1px solid rgba(255, 255, 255, 0.2)';
    title.style.paddingBottom = '10px';
    debugPanel.appendChild(title);

    // 添加API状态信息
    const statusInfo = document.createElement('div');
    statusInfo.style.marginBottom = '20px';
    statusInfo.style.padding = '10px';
    statusInfo.style.backgroundColor = 'rgba(255, 255, 255, 0.1)';
    statusInfo.style.borderRadius = '4px';

    let statusText = '';

    // 检查window对象
    statusText += `<p>Window对象: <span style="color: #22c55e;">存在</span></p>`;

    // 检查新API
    if (typeof window !== 'undefined' && window.electron) {
      statusText += `<p>新Electron API: <span style="color: #22c55e;">可用</span></p>`;

      // 列出可用方法
      statusText += '<p>可用方法:</p><ul>';
      // @ts-ignore - 动态访问属性
      for (const key in window.electron) {
        // @ts-ignore - 动态访问属性
        statusText += `<li>${key}: ${typeof window.electron[key]}</li>`;
      }
      statusText += '</ul>';

      // 版本信息
      try {
        // @ts-ignore - 动态访问属性
        const nodeVersion = window.electron.versions.node();
        // @ts-ignore - 动态访问属性
        const chromeVersion = window.electron.versions.chrome();
        // @ts-ignore - 动态访问属性
        const electronVersion = window.electron.versions.electron();

        statusText += `<p>Node版本: ${nodeVersion}</p>`;
        statusText += `<p>Chrome版本: ${chromeVersion}</p>`;
        statusText += `<p>Electron版本: ${electronVersion}</p>`;
      } catch (error) {
        statusText += `<p style="color: #ef4444;">获取版本信息失败</p>`;
      }
    } else {
      statusText += `<p>新Electron API: <span style="color: #ef4444;">不可用</span></p>`;
    }

    // 检查旧API
    if (typeof window !== 'undefined' && window.electronAPI) {
      statusText += `<p>旧Electron API: <span style="color: #22c55e;">可用</span></p>`;

      // 列出可用方法
      statusText += '<p>可用方法:</p><ul>';
      // @ts-ignore - 动态访问属性
      for (const key in window.electronAPI) {
        // @ts-ignore - 动态访问属性
        statusText += `<li>${key}: ${typeof window.electronAPI[key]}</li>`;
      }
      statusText += '</ul>';
    } else {
      statusText += `<p>旧Electron API: <span style="color: #ef4444;">不可用</span></p>`;
    }

    statusInfo.innerHTML = statusText;
    debugPanel.appendChild(statusInfo);

    // 添加测试按钮
    const testButtonsContainer = document.createElement('div');
    testButtonsContainer.style.display = 'flex';
    testButtonsContainer.style.flexDirection = 'column';
    testButtonsContainer.style.gap = '10px';

    // 测试新API按钮
    if (typeof window !== 'undefined' && window.electron) {
      const testNewApiButton = document.createElement('button');
      testNewApiButton.textContent = '测试新API文件选择';
      testNewApiButton.style.backgroundColor = '#3b82f6';
      testNewApiButton.style.color = 'white';
      testNewApiButton.style.border = 'none';
      testNewApiButton.style.borderRadius = '4px';
      testNewApiButton.style.padding = '8px 15px';
      testNewApiButton.style.cursor = 'pointer';

      testNewApiButton.addEventListener('click', async () => {
        try {
          // @ts-ignore - 动态访问属性
          const result = await window.electron.openFile();

          // 显示结果
          const resultElement = document.createElement('div');
          resultElement.style.marginTop = '15px';
          resultElement.style.padding = '10px';
          resultElement.style.backgroundColor = 'rgba(0, 255, 0, 0.1)';
          resultElement.style.borderRadius = '4px';
          resultElement.style.maxHeight = '200px';
          resultElement.style.overflow = 'auto';
          resultElement.style.wordBreak = 'break-all';
          resultElement.innerHTML = `<p>新API结果:</p><pre>${JSON.stringify(result, null, 2)}</pre>`;

          // 如果已有结果，则替换
          const existingResult = debugPanel.querySelector('.result-element');
          if (existingResult) {
            debugPanel.replaceChild(resultElement, existingResult);
          } else {
            debugPanel.appendChild(resultElement);
          }

          resultElement.className = 'result-element';
        } catch (error: any) {
          // 显示错误
          const errorElement = document.createElement('div');
          errorElement.style.marginTop = '15px';
          errorElement.style.padding = '10px';
          errorElement.style.backgroundColor = 'rgba(255, 0, 0, 0.1)';
          errorElement.style.borderRadius = '4px';
          errorElement.style.color = '#ff6b6b';
          errorElement.innerHTML = `<p>新API错误:</p><pre>${error.message || '未知错误'}</pre>`;

          // 如果已有结果，则替换
          const existingResult = debugPanel.querySelector('.result-element');
          if (existingResult) {
            debugPanel.replaceChild(errorElement, existingResult);
          } else {
            debugPanel.appendChild(errorElement);
          }

          errorElement.className = 'result-element';
        }
      });

      testButtonsContainer.appendChild(testNewApiButton);
    }

    // 测试旧API按钮
    if (typeof window !== 'undefined' && window.electronAPI) {
      const testOldApiButton = document.createElement('button');
      testOldApiButton.textContent = '测试旧API文件选择';
      testOldApiButton.style.backgroundColor = '#6b7280';
      testOldApiButton.style.color = 'white';
      testOldApiButton.style.border = 'none';
      testOldApiButton.style.borderRadius = '4px';
      testOldApiButton.style.padding = '8px 15px';
      testOldApiButton.style.cursor = 'pointer';

      testOldApiButton.addEventListener('click', async () => {
        try {
          // @ts-ignore - 动态访问属性
          const result = await window.electronAPI.selectFile();

          // 显示结果
          const resultElement = document.createElement('div');
          resultElement.style.marginTop = '15px';
          resultElement.style.padding = '10px';
          resultElement.style.backgroundColor = 'rgba(0, 255, 0, 0.1)';
          resultElement.style.borderRadius = '4px';
          resultElement.style.maxHeight = '200px';
          resultElement.style.overflow = 'auto';
          resultElement.style.wordBreak = 'break-all';
          resultElement.innerHTML = `<p>旧API结果:</p><pre>${JSON.stringify(result, null, 2)}</pre>`;

          // 如果已有结果，则替换
          const existingResult = debugPanel.querySelector('.result-element');
          if (existingResult) {
            debugPanel.replaceChild(resultElement, existingResult);
          } else {
            debugPanel.appendChild(resultElement);
          }

          resultElement.className = 'result-element';
        } catch (error: any) {
          // 显示错误
          const errorElement = document.createElement('div');
          errorElement.style.marginTop = '15px';
          errorElement.style.padding = '10px';
          errorElement.style.backgroundColor = 'rgba(255, 0, 0, 0.1)';
          errorElement.style.borderRadius = '4px';
          errorElement.style.color = '#ff6b6b';
          errorElement.innerHTML = `<p>旧API错误:</p><pre>${error.message || '未知错误'}</pre>`;

          // 如果已有结果，则替换
          const existingResult = debugPanel.querySelector('.result-element');
          if (existingResult) {
            debugPanel.replaceChild(errorElement, existingResult);
          } else {
            debugPanel.appendChild(errorElement);
          }

          errorElement.className = 'result-element';
        }
      });

      testButtonsContainer.appendChild(testOldApiButton);
    }

    debugPanel.appendChild(testButtonsContainer);

    // 添加关闭按钮
    const closeButton = document.createElement('button');
    closeButton.textContent = '关闭';
    closeButton.style.backgroundColor = '#ef4444';
    closeButton.style.color = 'white';
    closeButton.style.border = 'none';
    closeButton.style.borderRadius = '4px';
    closeButton.style.padding = '8px 15px';
    closeButton.style.marginTop = '20px';
    closeButton.style.cursor = 'pointer';
    closeButton.style.width = '100%';

    closeButton.addEventListener('click', () => {
      document.body.removeChild(debugPanel);
    });

    debugPanel.appendChild(closeButton);
    document.body.appendChild(debugPanel);
  };

  return (
    <div style={{
      maxWidth: '1200px',
      margin: '0 auto',
      padding: '20px',
      color: darkMode ? '#e0e0e0' : '#333',
      transition: 'all 0.3s ease'
    }}>
      <div style={{
        position: 'fixed',
        top: '10px',
        right: '10px',
        zIndex: 1000
      }}>
        <button
          onClick={toggleDarkMode}
          style={{
            backgroundColor: darkMode ? '#f0f0f0' : '#333',
            color: darkMode ? '#333' : '#f0f0f0',
            border: 'none',
            borderRadius: '50%',
            width: '40px',
            height: '40px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            fontSize: '20px',
            boxShadow: '0 2px 5px rgba(0,0,0,0.2)',
            transition: 'all 0.3s ease'
          }}
          title={darkMode ? '切换到日间模式' : '切换到夜间模式'}
        >
          {darkMode ? '☀️' : '🌙'}
        </button>
      </div>
      <h1 style={{
        textAlign: 'center',
        marginBottom: '30px',
        color: darkMode ? '#e0e0e0' : '#333'
      }}>USD 文件分析工具</h1>

      {/* 拖拽区域 */}
      <div
        {...getRootProps()}
        data-dropzone="true"
        style={{
          border: isDragActive
            ? '2px dashed #3b82f6'
            : `2px dashed ${darkMode ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.2)'}`,
          borderRadius: '8px',
          padding: '30px 20px',
          textAlign: 'center',
          transition: 'all 0.3s ease',
          background: isDragActive
            ? 'rgba(59, 130, 246, 0.05)'
            : darkMode ? 'rgba(255, 255, 255, 0.03)' : 'rgba(0, 0, 0, 0.02)',
          cursor: 'pointer',
          marginBottom: '20px'
        }}
      >
        <input {...getInputProps()} />
        <div style={{ marginBottom: '10px', fontSize: '18px', color: darkMode ? '#e0e0e0' : '#333' }}>
          {isDragActive ? (
            <p>将文件放在这里...</p>
          ) : (
            <p>将USD文件拖放到这里，或点击选择文件</p>
          )}
        </div>
        <p style={{
          fontSize: '14px',
          color: darkMode ? 'rgba(255, 255, 255, 0.5)' : 'rgba(0, 0, 0, 0.5)'
        }}>支持 .usd, .usda 和 .usdc 文件</p>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <label htmlFor="filePath" style={{
          display: 'block',
          marginBottom: '5px',
          color: darkMode ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)'
        }}>
          文件完整路径:
        </label>
        <div style={{ display: 'flex', gap: '10px' }}>
          <input
            id="filePath"
            type="text"
            value={filePath}
            onChange={(e) => setFilePath(e.target.value)}
            style={{
              flex: 1,
              padding: '8px',
              borderRadius: '4px',
              border: darkMode ? '1px solid rgba(255, 255, 255, 0.2)' : '1px solid rgba(0, 0, 0, 0.2)',
              background: darkMode ? '#333' : 'white',
              color: darkMode ? '#e0e0e0' : '#333'
            }}
            placeholder="输入USD文件的完整路径，例如: C:/Projects/MyUsdProject/assets/model.usda"
          />
          <button
            onClick={openFileBrowser}
            style={{
              backgroundColor: darkMode ? '#555' : '#4b5563',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              padding: '0 20px',
              cursor: 'pointer',
              fontSize: '16px',
              transition: 'all 0.3s ease'
            }}
            id="select-file-button"
          >
            选择文件
          </button>

          <button
            onClick={startAnalysis}
            style={{
              backgroundColor: '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              padding: '0 20px',
              cursor: 'pointer',
              fontSize: '16px',
              transition: 'all 0.3s ease'
            }}
            id="start-analysis-button"
          >
            开始分析
          </button>
        </div>
      </div>



      {error && (
        <div style={{
          background: darkMode ? 'rgba(239, 68, 68, 0.2)' : 'rgba(239, 68, 68, 0.1)',
          borderLeft: '4px solid #ef4444',
          padding: '15px',
          borderRadius: '4px',
          margin: '20px 0',
          color: darkMode ? '#ff8a8a' : '#fca5a5'
        }}>
          <p>{error}</p>
        </div>
      )}

      {isLoading && (
        <div style={{ textAlign: 'center', margin: '30px 0' }}>
          <div style={{
            border: `3px solid ${darkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'}`,
            borderTop: '3px solid #3b82f6',
            borderRadius: '50%',
            width: '30px',
            height: '30px',
            animation: 'spin 1s linear infinite',
            margin: '0 auto 15px'
          }}></div>
          <p style={{ color: darkMode ? '#e0e0e0' : '#333' }}>正在分析文件...</p>
        </div>
      )}

      <div style={{ display: 'flex', marginTop: '20px' }}>
        {/* 左侧分析历史列表 */}
        <div style={{
          width: '250px',
          marginRight: '20px',
          background: darkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.03)',
          borderRadius: '8px',
          overflow: 'hidden',
          border: darkMode ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.1)',
          transition: 'all 0.3s ease'
        }}>
          <div style={{
            padding: '15px',
            borderBottom: darkMode ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.1)',
            fontWeight: 'bold',
            fontSize: '16px',
            color: darkMode ? '#e0e0e0' : '#333',
            transition: 'all 0.3s ease'
          }}>
            分析历史
          </div>

          <div style={{ height: 'calc(100vh - 250px)', overflowY: 'auto' }}>
            {results.length === 0 ? (
              <div style={{
                padding: '15px',
                color: darkMode ? 'rgba(255, 255, 255, 0.5)' : '#9ca3af',
                textAlign: 'center'
              }}>
                暂无分析记录
              </div>
            ) : (
              results.map((result, index) => (
                <div
                  key={`history-${index}`}
                  onClick={() => {
                    setSelectedResult(result);
                    setShowReferences(false);
                    setShowTextures(false);
                  }}
                  style={{
                    padding: '12px 15px',
                    borderBottom: darkMode ? '1px solid rgba(255, 255, 255, 0.05)' : '1px solid rgba(0, 0, 0, 0.05)',
                    cursor: 'pointer',
                    background: selectedResult === result
                      ? darkMode ? 'rgba(59, 130, 246, 0.2)' : 'rgba(59, 130, 246, 0.1)'
                      : 'transparent',
                    position: 'relative',
                    transition: 'all 0.2s ease'
                  }}
                  onMouseEnter={e => {
                    if (selectedResult !== result) {
                      e.currentTarget.style.background = darkMode
                        ? 'rgba(255, 255, 255, 0.05)'
                        : 'rgba(0, 0, 0, 0.05)';
                    }
                  }}
                  onMouseLeave={e => {
                    if (selectedResult !== result) {
                      e.currentTarget.style.background = 'transparent';
                    }
                  }}
                >
                  <div style={{
                    fontSize: '14px',
                    fontWeight: '500',
                    marginBottom: '5px',
                    wordBreak: 'break-all',
                    color: darkMode ? '#e0e0e0' : 'inherit'
                  }}>
                    {result.filename}
                  </div>
                  <div style={{
                    fontSize: '12px',
                    color: darkMode ? 'rgba(255, 255, 255, 0.5)' : '#9ca3af'
                  }}>
                    {result.timestamp || '无时间记录'}
                  </div>
                  {selectedResult === result && (
                    <div style={{
                      position: 'absolute',
                      left: 0,
                      top: 0,
                      bottom: 0,
                      width: '3px',
                      background: '#3b82f6'
                    }}></div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* 右侧主内容区 */}
        <div style={{ flex: 1 }}>
          {selectedResult ? (
            <div>
              <h2 style={{
                fontSize: '24px',
                marginBottom: '15px',
                color: darkMode ? '#e0e0e0' : 'inherit'
              }}>{selectedResult.filename}</h2>

              {selectedResult.analysis.success ? (
                <>
                  {/* 一键打包功能区域 */}
                  <div style={{
                    background: darkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.03)',
                    borderRadius: '8px',
                    padding: '15px',
                    margin: '20px 0',
                    border: darkMode ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.1)',
                    transition: 'all 0.3s ease'
                  }}>
                    <h3 style={{
                      fontSize: '18px',
                      marginBottom: '10px',
                      color: darkMode ? '#e0e0e0' : 'inherit'
                    }}>一键打包</h3>
                    <div style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
                      <input
                        type="text"
                        value={outputPath}
                        onChange={(e) => setOutputPath(e.target.value)}
                        placeholder="输入输出路径，例如: E:\\output\\folder"
                        style={{
                          flex: 1,
                          padding: '8px',
                          borderRadius: '4px',
                          border: darkMode ? '1px solid rgba(255, 255, 255, 0.2)' : '1px solid rgba(0, 0, 0, 0.2)',
                          background: darkMode ? '#333' : 'white',
                          color: darkMode ? '#e0e0e0' : '#333',
                          transition: 'all 0.3s ease'
                        }}
                      />
                      <button
                        onClick={packageFiles}
                        disabled={isPackaging}
                        style={{
                          backgroundColor: '#ef4444',
                          color: 'white',
                          border: 'none',
                          borderRadius: '4px',
                          padding: '0 20px',
                          cursor: isPackaging ? 'not-allowed' : 'pointer',
                          fontSize: '16px',
                          opacity: isPackaging ? 0.7 : 1
                        }}
                      >
                        {isPackaging ? '打包中...' : '一键打包'}
                      </button>
                    </div>
                    {packageResult && (
                      <div style={{
                        background: packageResult.success ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                        borderLeft: `4px solid ${packageResult.success ? '#22c55e' : '#ef4444'}`,
                        padding: '10px',
                        borderRadius: '4px',
                        marginTop: '10px',
                        color: packageResult.success ? '#166534' : '#b91c1c'
                      }}>
                        <p>{packageResult.message}</p>
                      </div>
                    )}
                  </div>

                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                    gap: '15px',
                    margin: '20px 0'
                  }}>
                    <div
                      onClick={() => {
                        setShowReferences(!showReferences);
                        if (!showReferences) setShowTextures(false);
                      }}
                      style={{
                        background: showReferences
                          ? darkMode ? 'rgba(59, 130, 246, 0.2)' : 'rgba(59, 130, 246, 0.1)'
                          : darkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.03)',
                        borderRadius: '8px',
                        padding: '15px',
                        textAlign: 'center',
                        border: showReferences
                          ? '1px solid rgba(59, 130, 246, 0.3)'
                          : darkMode ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.1)',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.transform = 'translateY(-2px)';
                        e.currentTarget.style.boxShadow = darkMode
                          ? '0 4px 6px rgba(255, 255, 255, 0.1)'
                          : '0 4px 6px rgba(0, 0, 0, 0.1)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.transform = 'translateY(0)';
                        e.currentTarget.style.boxShadow = 'none';
                      }}
                    >
                      <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#3b82f6' }}>
                        {selectedResult.analysis.references.length}
                      </div>
                      <div style={{
                        fontSize: '14px',
                        color: darkMode ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)'
                      }}>
                        引用数量 {showReferences ? '▼' : '►'}
                      </div>
                    </div>
                    <div
                      onClick={() => {
                        setShowTextures(!showTextures);
                        if (!showTextures) setShowReferences(false);
                      }}
                      style={{
                        background: showTextures
                          ? darkMode ? 'rgba(59, 130, 246, 0.2)' : 'rgba(59, 130, 246, 0.1)'
                          : darkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.03)',
                        borderRadius: '8px',
                        padding: '15px',
                        textAlign: 'center',
                        border: showTextures
                          ? '1px solid rgba(59, 130, 246, 0.3)'
                          : darkMode ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid rgba(0, 0, 0, 0.1)',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.transform = 'translateY(-2px)';
                        e.currentTarget.style.boxShadow = darkMode
                          ? '0 4px 6px rgba(255, 255, 255, 0.1)'
                          : '0 4px 6px rgba(0, 0, 0, 0.1)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.transform = 'translateY(0)';
                        e.currentTarget.style.boxShadow = 'none';
                      }}
                    >
                      <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#3b82f6' }}>
                        {selectedResult.analysis.textures.length}
                      </div>
                      <div style={{
                        fontSize: '14px',
                        color: darkMode ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)'
                      }}>
                        纹理数量 {showTextures ? '▼' : '►'}
                      </div>
                    </div>
                  </div>

              {showReferences && (
                <div style={{
                  marginTop: '25px',
                  animation: 'fadeIn 0.3s ease-in-out'
                }}>
                  <h3 style={{ fontSize: '20px', marginBottom: '15px' }}>引用列表</h3>
                  {selectedResult.analysis.references.map((ref, refIndex) => (
                    <div
                      key={`${ref.path}-${refIndex}`}
                      style={{
                        background: 'rgba(0, 0, 0, 0.03)',
                        borderRadius: '8px',
                        padding: '15px',
                        margin: '10px 0',
                        transition: 'transform 0.2s ease',
                        border: '1px solid rgba(0, 0, 0, 0.1)'
                      }}
                      onMouseEnter={e => {
                        (e.currentTarget as HTMLDivElement).style.transform = 'translateX(4px)';
                        (e.currentTarget as HTMLDivElement).style.background = 'rgba(0, 0, 0, 0.05)';
                      }}
                      onMouseLeave={e => {
                        (e.currentTarget as HTMLDivElement).style.transform = 'translateX(0)';
                        (e.currentTarget as HTMLDivElement).style.background = 'rgba(0, 0, 0, 0.03)';
                      }}
                    >
                      <p style={{ fontWeight: '500', marginBottom: '5px', wordBreak: 'break-all' }}>{ref.path}</p>
                      <p style={{ fontSize: '14px', color: '#666' }}>类型: {ref.type}</p>
                      <p style={{ fontSize: '14px', color: '#666' }}>Prim路径: {ref.prim_path}</p>
                    </div>
                  ))}
                </div>
              )}

              {showTextures && selectedResult.analysis.textures.length > 0 && (
                <div style={{
                  marginTop: '25px',
                  animation: 'fadeIn 0.3s ease-in-out'
                }}>
                  <h3 style={{ fontSize: '20px', marginBottom: '15px' }}>纹理列表</h3>

                  {/* 按照引用USD文件分组显示纹理 */}
                  {(() => {
                    // 按照shader（引用USD文件）分组
                    const textureGroups: Record<string, Texture[]> = {};

                    // 分组处理
                    selectedResult.analysis.textures.forEach(texture => {
                      // 从贴图路径中提取正确的文件夹名称
                      let shaderKey = '未知来源';

                      if (texture.source) {
                        // 如果source包含冒号，说明是"shader:input"或"main.usda:UDIM"格式
                        const sourceParts = texture.source.split(':');
                        if (sourceParts.length > 0) {
                          shaderKey = sourceParts[0];
                        }
                      }

                      // 如果路径中包含USD/shader/或USD/mdl/，提取父级文件夹名称
                      if (texture.path) {
                        const path = texture.path.replace(/\\/g, '/');

                        // 尝试从路径中提取父级文件夹名称
                        const usdMatch = path.match(/\/env\/test\/([^\/]+)\/USD\/(shader|mdl)/);
                        if (usdMatch && usdMatch[1]) {
                          // 使用父级文件夹名称作为主分组
                          const parentFolder = usdMatch[1];
                          shaderKey = parentFolder;
                        }
                      }

                      // 创建分组
                      if (!textureGroups[shaderKey]) {
                        textureGroups[shaderKey] = [];
                      }
                      textureGroups[shaderKey].push(texture);
                    });

                    // 检查是否有任何分组
                    if (Object.keys(textureGroups).length === 0) {
                      return (
                        <div style={{
                          background: 'rgba(0, 0, 0, 0.03)',
                          borderRadius: '8px',
                          padding: '15px',
                          margin: '10px 0',
                          textAlign: 'center',
                          color: '#666',
                          border: '1px solid rgba(0, 0, 0, 0.1)'
                        }}>
                          没有找到贴图分组信息
                        </div>
                      );
                    }

                    // 渲染分组后的纹理
                    return Object.entries(textureGroups).map(([shaderKey, textures], groupIndex) => {
                      // 生成唯一的组ID
                      const groupId = `${selectedResult.filename}-${shaderKey}-${groupIndex}`;

                      // 如果该组的状态未初始化，则默认为展开
                      if (expandedGroups[groupId] === undefined) {
                        setExpandedGroups(prev => ({
                          ...prev,
                          [groupId]: true
                        }));
                      }

                      // 切换展开/折叠状态的处理函数
                      const toggleExpand = () => {
                        setExpandedGroups(prev => ({
                          ...prev,
                          [groupId]: !prev[groupId]
                        }));
                      };

                      return (
                        <div key={`group-${groupIndex}`} style={{ marginBottom: '15px' }}>
                          {/* 父级（可折叠标题） */}
                          <div
                            onClick={toggleExpand}
                            style={{
                              background: 'rgba(59, 130, 246, 0.1)',
                              borderRadius: '8px',
                              padding: '12px 15px',
                              cursor: 'pointer',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              transition: 'background 0.2s ease',
                              border: '1px solid rgba(59, 130, 246, 0.2)'
                            }}
                            onMouseEnter={e => {
                              e.currentTarget.style.background = 'rgba(59, 130, 246, 0.2)';
                            }}
                            onMouseLeave={e => {
                              e.currentTarget.style.background = 'rgba(59, 130, 246, 0.1)';
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center' }}>
                              <span style={{ marginRight: '10px', fontSize: '18px' }}>
                                {expandedGroups[groupId] ? '▼' : '►'}
                              </span>
                              <span style={{ fontWeight: '500', wordBreak: 'break-all' }}>
                                {shaderKey}
                              </span>
                            </div>
                            <span style={{
                              background: 'rgba(59, 130, 246, 0.2)',
                              borderRadius: '12px',
                              padding: '2px 8px',
                              fontSize: '14px'
                            }}>
                              {textures.length}
                            </span>
                          </div>

                          {/* 子级（贴图列表） */}
                          {expandedGroups[groupId] && (
                            <div style={{
                              marginLeft: '20px',
                              borderLeft: '2px solid rgba(59, 130, 246, 0.3)',
                              paddingLeft: '15px'
                            }}>
                              {textures.map((texture, texIndex) => (
                                <div
                                  key={`${texture.path}-${texIndex}`}
                                  style={{
                                    background: 'rgba(0, 0, 0, 0.03)',
                                    borderRadius: '8px',
                                    padding: '15px',
                                    margin: '10px 0',
                                    transition: 'transform 0.2s ease',
                                    borderLeft: texture.exists === false ? '4px solid #ef4444' : undefined,
                                    border: '1px solid rgba(0, 0, 0, 0.1)'
                                  }}
                                  onMouseEnter={e => {
                                    (e.currentTarget as HTMLDivElement).style.transform = 'translateX(4px)';
                                    (e.currentTarget as HTMLDivElement).style.background = 'rgba(0, 0, 0, 0.05)';
                                  }}
                                  onMouseLeave={e => {
                                    (e.currentTarget as HTMLDivElement).style.transform = 'translateX(0)';
                                    (e.currentTarget as HTMLDivElement).style.background = 'rgba(0, 0, 0, 0.03)';
                                  }}
                                >
                                  <span style={{ fontWeight: '500', wordBreak: 'break-all' }}>
                                    {texture.path}
                                  </span>
                                  <p style={{
                                    fontSize: '14px',
                                    color: '#b45309',
                                    margin: '5px 0',
                                    padding: 0
                                  }}>
                                    贴图数量：
                                    {(() => {
                                      // 检查是否是UDIM贴图
                                      const isUdim = texture.path && (
                                        texture.path.includes('<UDIM>') ||
                                        texture.path.includes('<udim>') ||
                                        texture.path.includes('.####.') ||
                                        texture.path.includes('.<UDIM>.') ||
                                        texture.path.includes('.<udim>.')
                                      );

                                      // 首先检查texture对象中是否有actual_texture_count属性
                                      if ('actual_texture_count' in texture && texture.actual_texture_count !== undefined) {
                                        return texture.actual_texture_count;
                                      }

                                      // 如果是UDIM贴图，从texture_udim_counts中获取数量
                                      if (isUdim && selectedResult.analysis.texture_udim_counts) {
                                        // 尝试不同的路径格式来匹配texture_udim_counts中的键
                                        const normalizedPath = texture.path.replace(/\\/g, '/');
                                        const alternativePath = texture.path.replace(/\//g, '\\');

                                        // 检查各种可能的路径格式
                                        if (selectedResult.analysis.texture_udim_counts[texture.path]) {
                                          return selectedResult.analysis.texture_udim_counts[texture.path];
                                        } else if (selectedResult.analysis.texture_udim_counts[normalizedPath]) {
                                          return selectedResult.analysis.texture_udim_counts[normalizedPath];
                                        } else if (selectedResult.analysis.texture_udim_counts[alternativePath]) {
                                          return selectedResult.analysis.texture_udim_counts[alternativePath];
                                        }

                                        // 如果找不到精确匹配，尝试部分匹配
                                        const udimCountsEntries = Object.entries(selectedResult.analysis.texture_udim_counts);
                                        for (const [countPath, count] of udimCountsEntries) {
                                          // 提取文件名部分进行比较
                                          const texFileName = texture.path.split(/[\\/]/).pop() || '';
                                          const countFileName = countPath.split(/[\\/]/).pop() || '';

                                          if (texFileName === countFileName ||
                                              countPath.includes(texFileName) ||
                                              texFileName.includes(countFileName)) {
                                            console.log(`找到UDIM贴图匹配: ${texFileName} -> ${countFileName}, 数量: ${count}`);
                                            return count;
                                          }
                                        }
                                      }

                                      // 否则返回默认值1
                                      return isUdim ? '未知' : '1';
                                    })()}
                                  </p>
                                  {texture.udim_count !== undefined && texture.udim_count > 0 && (
                                    <p style={{ fontSize: '14px', color: '#666' }}>UDIM数量: {texture.udim_count}</p>
                                  )}
                                  {texture.exists === false && (
                                    <p style={{ fontSize: '14px', color: '#ef4444' }}>文件不存在</p>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    });
                  })()}
                </div>
              )}
            </>
          ) : (
            <div style={{
              background: 'rgba(239, 68, 68, 0.1)',
              borderLeft: '4px solid #ef4444',
              padding: '15px',
              borderRadius: '4px',
              margin: '20px 0',
              color: '#fca5a5'
            }}>
              <p>分析失败: {selectedResult.analysis.error}</p>
            </div>
          )}
            </div>
          ) : results.length > 0 ? (
            <div style={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              height: '300px',
              background: 'rgba(255, 255, 255, 0.03)',
              borderRadius: '8px',
              color: '#9ca3af'
            }}>
              请从左侧选择一个分析结果查看详情
            </div>
          ) : (
            <div style={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              height: '300px',
              background: 'rgba(255, 255, 255, 0.03)',
              borderRadius: '8px',
              color: '#9ca3af'
            }}>
              请先分析USD文件
            </div>
          )}
        </div>
      </div>

      <FileBrowser />

      {/* 添加CSS动画和全局样式 */}
      <style jsx global>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        @keyframes fadeIn {
          0% { opacity: 0; transform: translateY(10px); }
          100% { opacity: 1; transform: translateY(0); }
        }
        html, body {
          margin: 0;
          padding: 0;
          width: 100%;
          height: 100%;
          background-color: ${darkMode ? '#1a1a1a' : '#ffffff'};
          color: ${darkMode ? '#e0e0e0' : '#333'};
          transition: all 0.3s ease;
        }
        * {
          box-sizing: border-box;
        }
      `}</style>
    </div>
  );
}