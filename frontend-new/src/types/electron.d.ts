// 为Electron API添加类型声明
interface ElectronAPI {
  selectFile: () => Promise<{ canceled: boolean; filePaths: string[] }>;
  startAnalysis: () => Promise<{ success: boolean; error?: string }>;
  onFileSelected: (callback: (filePath: string) => void) => () => void;
  isElectron: boolean;
}

// 扩展Window接口
declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}

export {};
