// API URL utility for both web and Electron environments
import axios from 'axios';

// 检测是否在Electron环境中运行
const isElectron = () => {
  // Renderer process
  if (typeof window !== 'undefined' && typeof window.process === 'object' &&
      // @ts-ignore - 在Electron环境中，process对象会有type属性
      window.process.type === 'renderer') {
    return true;
  }

  // Main process
  if (typeof process !== 'undefined' && typeof process.versions === 'object' &&
      // @ts-ignore - 在Electron环境中，process.versions会有electron属性
      !!process.versions.electron) {
    return true;
  }

  // Detect the user agent when the `nodeIntegration` option is set to false
  if (typeof navigator === 'object' && typeof navigator.userAgent === 'string' &&
      navigator.userAgent.indexOf('Electron') >= 0) {
    return true;
  }

  return false;
};

// 获取API基础URL - 简化版本，避免服务器端渲染问题
export const getApiBaseUrl = () => {
  // 固定使用端口63080
  const baseUrl = 'http://localhost:63080';
  console.log('API基础URL:', baseUrl);
  return baseUrl;
};

// 创建一个axios实例
export const api = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 30000, // 30秒超时
  headers: {
    'Content-Type': 'application/json',
  },
});

// 添加请求拦截器
api.interceptors.request.use(
  config => {
    console.log(`发送请求: ${config.method?.toUpperCase()} ${config.url}`, config);
    return config;
  },
  error => {
    console.error('请求错误:', error);
    return Promise.reject(error);
  }
);

// 添加响应拦截器
api.interceptors.response.use(
  response => {
    console.log(`收到响应: ${response.status} ${response.config.url}`, response.data);
    return response;
  },
  error => {
    console.error('响应错误:', error);
    if (error.response) {
      console.error('错误状态码:', error.response.status);
      console.error('错误数据:', error.response.data);
    } else if (error.request) {
      console.error('未收到响应，请求信息:', error.request);
    } else {
      console.error('请求配置错误:', error.message);
    }
    return Promise.reject(error);
  }
);

// 导出API函数
export const apiService = {
  // 分析文件路径
  analyzeFilePath: async (filePath: string) => {
    try {
      // 确保文件路径格式正确
      const cleanPath = filePath.trim();
      console.log('准备发送分析请求，文件路径:', cleanPath);

      // 创建FormData对象
      const formData = new FormData();

      // 确保只添加一次文件路径，避免重复
      formData.append('file_path', cleanPath);

      // 打印FormData内容进行调试
      console.log('FormData内容:', formData.get('file_path'));

      // 检查后端连接
      try {
        console.log('检查后端连接...');
        const checkResponse = await fetch('http://localhost:63080/browse_directory');
        if (!checkResponse.ok) {
          throw new Error(`后端服务响应异常: ${checkResponse.status}`);
        }
        console.log('后端连接正常，继续发送分析请求');
      } catch (error: any) {
        console.error('后端连接检查失败:', error);
        throw new Error(`后端连接失败，无法发送分析请求: ${error.message}`);
      }

      // 发送请求
      console.log('开始发送分析请求...');
      const response = await api.post('/analyze_path', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 60000, // 增加超时时间到60秒
      });
      console.log('分析请求发送成功，收到响应');

      // 验证响应数据格式
      if (!response.data) {
        console.error('API返回的数据为空');
        throw new Error('API返回的数据为空');
      }

      console.log('API响应数据:', response.data);

      if (!response.data.analysis) {
        console.error('API返回的数据缺少analysis字段:', response.data);
        // 添加缺失的字段以避免前端错误
        response.data.analysis = {
          success: false,
          error: '服务器返回的数据格式不正确',
          textures: [],
          references: []
        };
      }

      return response;
    } catch (error: any) {
      console.error('API调用失败:', error);

      // 添加更详细的错误信息
      if (error.response) {
        console.error('错误响应状态码:', error.response.status);
        console.error('错误响应数据:', error.response.data);
        throw new Error(`API调用失败 (${error.response.status}): ${error.response.data?.detail || error.message}`);
      } else if (error.request) {
        console.error('未收到响应，请求信息:', error.request);
        throw new Error(`API调用失败，未收到响应: ${error.message}`);
      } else {
        console.error('请求配置错误:', error.message);
        throw new Error(`API调用失败，请求配置错误: ${error.message}`);
      }
    }
  },

  // 浏览目录
  browseDirectory: async (directoryPath: string = "") => {
    return api.get('/browse_directory', {
      params: { directory_path: directoryPath }
    });
  },

  // 打包文件
  packageFile: async (filePath: string, outputPath: string, textures: any[], references: any[]) => {
    return api.post('/package', {
      file_path: filePath,
      output_path: outputPath,
      textures: textures,
      references: references
    });
  }
};

export default apiService;
