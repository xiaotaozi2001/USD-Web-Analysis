// 声明全局类型
interface Window {
  // 新的Electron API
  electron?: {
    openFile: () => Promise<any>;
    getFilePath: (relativePath: string) => Promise<{success: boolean; path?: string; error?: string}>;
    handleFileDrop: (files: File[] | FileList) => {success: boolean; path?: string; error?: string};
    registerFileDropHandler: (callback: (fileInfo: {path: string; name: string}) => void) => Promise<{success: boolean}>;
    startAnalysis: () => Promise<any>;
    versions: {
      node: () => string;
      chrome: () => string;
      electron: () => string;
    };
    ping: () => string;
  };

  // 旧的API（保留以兼容现有代码）
  electronAPI?: ElectronAPI;
  electronAPIExposed?: boolean;
  __electron_debug__?: ElectronDebugAPI;
  __debug_openFileBrowser?: () => void;
  __debug_startAnalysis?: () => void;
  __debug_selectFile?: () => Promise<any>;
  __debug_openFileDialog?: () => Promise<any>;
  __debug_runAnalysis?: () => Promise<any>;
}

interface ElectronAPI {
  selectFile: () => Promise<any>;
  startAnalysis: () => Promise<any>;
  onFileSelected: (callback: (filePath: string) => void) => () => void;
  isElectron: boolean;
  getVersionInfo?: () => {
    electron: string;
    chrome: string;
    node: string;
  };
  openFileDialog?: () => Promise<any>;
  runAnalysis?: () => Promise<any>;
}

interface ElectronDebugAPI {
  selectFile: () => Promise<any>;
  startAnalysis: () => Promise<any>;
}
