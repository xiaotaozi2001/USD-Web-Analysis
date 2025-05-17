/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'export',  // 启用静态导出，用于Electron
  distDir: 'out',    // 指定输出目录
  images: {
    unoptimized: true, // 在静态导出中禁用图像优化
  },
  // 配置基本路径，在Electron中使用文件协议时需要
  basePath: '',
  assetPrefix: '/',
}

module.exports = nextConfig
