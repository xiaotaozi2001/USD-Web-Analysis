// 全局类型声明
interface Window {
  electronAPI?: {
    selectFile: () => Promise<any>;
    startAnalysis: () => Promise<any>;
    onFileSelected: (callback: (filePath: string) => void) => () => void;
    isElectron: boolean;
    getVersionInfo?: () => {
      electron: string;
      chrome: string;
      node: string;
    };
  };
  electronAPIExposed?: boolean;
}
