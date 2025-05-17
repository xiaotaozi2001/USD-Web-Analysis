from pxr import Usd, UsdGeom, UsdShade, Sdf, Ar
import os
import re
import glob
import logging
import traceback
from typing import Optional, List, Dict, Any, Set

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class EnhancedUsdAnalyzer:
    def __init__(self):
        """初始化分析器"""
        # 已处理的资产路径集合，用于避免循环引用
        self.processed_assets = set()
        # 存储所有发现的贴图路径及其来源
        self.texture_files = {}  # 改为字典，存储贴图路径及其来源
        # 存储所有引用的USD文件
        self.referenced_usd_files = set()
        # 存储引用路径和类型的元组列表
        self.references = []
        # 存储UDIM贴图序列的贴图数量
        self.texture_udim_counts = {}
    
    def reset(self):
        """重置分析器状态"""
        self.processed_assets = set()
        self.texture_files = {}  # 改为字典，存储贴图路径及其来源
        self.referenced_usd_files = set()
        self.references = []
        self.texture_udim_counts = {}  # 存储UDIM贴图序列的贴图数量
    
    def resolve_path(self, file_path, base_dir=None):
        """解析路径，将相对路径转换为绝对路径"""
        if not file_path:
            return None
            
        logger.info(f"解析路径: {file_path}, 基础目录: {base_dir}")
        
        # 如果已经是绝对路径，则直接返回
        if os.path.isabs(file_path):
            logger.info(f"已经是绝对路径: {file_path}")
            return file_path
            
        # 清理路径，移除引号和多余的空格
        file_path = file_path.strip().strip('"\'')
        
        # 处理UDIM路径
        is_udim = False
        udim_pattern = None
        for pattern in ['<UDIM>', '<udim>', '.####.', '.<UDIM>.', '.<udim>.']:
            if pattern in file_path:
                is_udim = True
                udim_pattern = pattern
                # 对于UDIM路径，我们需要替换占位符以便检查文件是否存在
                # 通常使用1001作为第一个UDIM索引
                test_path = file_path.replace(pattern, '.1001.')
                logger.info(f"UDIM路径: {file_path}, 测试路径: {test_path}")
                file_path = test_path
                break
                
        # 如果提供了基础目录，则尝试使用它来解析路径
        if base_dir:
            # 处理多级相对路径，如 ../../textures/file.jpg
            if file_path.startswith('../') or file_path.startswith('./'):
                # 计算实际路径
                full_path = os.path.normpath(os.path.join(base_dir, file_path))
                logger.info(f"多级相对路径: {file_path} -> {full_path}")
                
                # 检查文件是否存在
                if os.path.exists(full_path):
                    logger.info(f"文件存在: {full_path}")
                    if is_udim:
                        # 对于UDIM贴图，我们需要恢复原始的UDIM占位符
                        original_path = full_path.replace('.1001.', udim_pattern)
                        logger.info(f"恢复UDIM路径: {full_path} -> {original_path}")
                        return original_path
                    return full_path
                else:
                    logger.info(f"文件不存在: {full_path}")
                    
                    # 尝试在不同的位置查找文件
                    # 1. 检查是否有txt目录
                    txt_dir = os.path.join(os.path.dirname(base_dir), 'txt')
                    if os.path.exists(txt_dir):
                        # 提取文件名
                        file_name = os.path.basename(file_path)
                        # 在txt目录中查找
                        for root, dirs, files in os.walk(txt_dir):
                            for file in files:
                                if file == file_name or (is_udim and file.startswith(file_name.replace('.1001.', ''))):
                                    found_path = os.path.join(root, file)
                                    logger.info(f"在txt目录中找到文件: {found_path}")
                                    if is_udim:
                                        # 对于UDIM贴图，我们需要恢复原始的UDIM占位符
                                        dir_name = os.path.dirname(found_path)
                                        base_name = os.path.basename(file_path).replace('.1001.', '')
                                        original_path = os.path.join(dir_name, base_name.replace('.', udim_pattern + '.'))
                                        logger.info(f"恢复UDIM路径: {found_path} -> {original_path}")
                                        return original_path
                                    return found_path
                    
                    # 2. 尝试在publish目录中查找
                    publish_dir = os.path.join(os.path.dirname(base_dir), 'publish')
                    if os.path.exists(publish_dir):
                        # 提取文件名
                        file_name = os.path.basename(file_path)
                        # 在publish目录中查找
                        for root, dirs, files in os.walk(publish_dir):
                            for file in files:
                                if file == file_name or (is_udim and file.startswith(file_name.replace('.1001.', ''))):
                                    found_path = os.path.join(root, file)
                                    logger.info(f"在publish目录中找到文件: {found_path}")
                                    if is_udim:
                                        # 对于UDIM贴图，我们需要恢复原始的UDIM占位符
                                        dir_name = os.path.dirname(found_path)
                                        base_name = os.path.basename(file_path).replace('.1001.', '')
                                        original_path = os.path.join(dir_name, base_name.replace('.', udim_pattern + '.'))
                                        logger.info(f"恢复UDIM路径: {found_path} -> {original_path}")
                                        return original_path
                                    return found_path
                    
                    # 如果文件不存在，则尝试返回原始路径
                    if is_udim:
                        # 对于UDIM贴图，我们需要恢复原始的UDIM占位符
                        original_path = full_path.replace('.1001.', udim_pattern)
                        logger.info(f"文件不存在，返回原始UDIM路径: {original_path}")
                        return original_path
                    
                    logger.info(f"文件不存在，返回原始路径: {full_path}")
                    return full_path
            else:
                # 处理简单的相对路径，如 textures/file.jpg
                full_path = os.path.normpath(os.path.join(base_dir, file_path))
                logger.info(f"简单相对路径: {file_path} -> {full_path}")
                
                # 检查文件是否存在
                if os.path.exists(full_path):
                    logger.info(f"文件存在: {full_path}")
                    if is_udim:
                        # 对于UDIM贴图，我们需要恢复原始的UDIM占位符
                        original_path = full_path.replace('.1001.', udim_pattern)
                        logger.info(f"恢复UDIM路径: {full_path} -> {original_path}")
                        return original_path
                    return full_path
                else:
                    logger.info(f"文件不存在: {full_path}")
                    
                    # 尝试在不同的位置查找文件
                    # 1. 检查是否有txt目录
                    txt_dir = os.path.join(os.path.dirname(base_dir), 'txt')
                    if os.path.exists(txt_dir):
                        # 提取文件名
                        file_name = os.path.basename(file_path)
                        # 在txt目录中查找
                        for root, dirs, files in os.walk(txt_dir):
                            for file in files:
                                if file == file_name or (is_udim and file.startswith(file_name.replace('.1001.', ''))):
                                    found_path = os.path.join(root, file)
                                    logger.info(f"在txt目录中找到文件: {found_path}")
                                    if is_udim:
                                        # 对于UDIM贴图，我们需要恢复原始的UDIM占位符
                                        dir_name = os.path.dirname(found_path)
                                        base_name = os.path.basename(file_path).replace('.1001.', '')
                                        original_path = os.path.join(dir_name, base_name.replace('.', udim_pattern + '.'))
                                        logger.info(f"恢复UDIM路径: {found_path} -> {original_path}")
                                        return original_path
                                    return found_path
                    
                    # 2. 尝试在publish目录中查找
                    publish_dir = os.path.join(os.path.dirname(base_dir), 'publish')
                    if os.path.exists(publish_dir):
                        # 提取文件名
                        file_name = os.path.basename(file_path)
                        # 在publish目录中查找
                        for root, dirs, files in os.walk(publish_dir):
                            for file in files:
                                if file == file_name or (is_udim and file.startswith(file_name.replace('.1001.', ''))):
                                    found_path = os.path.join(root, file)
                                    logger.info(f"在publish目录中找到文件: {found_path}")
                                    if is_udim:
                                        # 对于UDIM贴图，我们需要恢复原始的UDIM占位符
                                        dir_name = os.path.dirname(found_path)
                                        base_name = os.path.basename(file_path).replace('.1001.', '')
                                        original_path = os.path.join(dir_name, base_name.replace('.', udim_pattern + '.'))
                                        logger.info(f"恢复UDIM路径: {found_path} -> {original_path}")
                                        return original_path
                                    return found_path
                    
                    # 如果文件不存在，则尝试返回原始路径
                    if is_udim:
                        # 对于UDIM贴图，我们需要恢复原始的UDIM占位符
                        original_path = full_path.replace('.1001.', udim_pattern)
                        logger.info(f"文件不存在，返回原始UDIM路径: {original_path}")
                        return original_path
                    
                    logger.info(f"文件不存在，返回原始路径: {full_path}")
                    return full_path
        
        # 如果没有提供基础目录，则尝试在当前工作目录中查找
        full_path = os.path.normpath(os.path.join(os.getcwd(), file_path))
        logger.info(f"使用当前工作目录: {file_path} -> {full_path}")
        
        # 检查文件是否存在
        if os.path.exists(full_path):
            logger.info(f"文件存在: {full_path}")
            if is_udim:
                # 对于UDIM贴图，我们需要恢复原始的UDIM占位符
                original_path = full_path.replace('.1001.', udim_pattern)
                logger.info(f"恢复UDIM路径: {full_path} -> {original_path}")
                return original_path
            return full_path
        else:
            logger.info(f"文件不存在: {full_path}")
            
            # 如果文件不存在，则尝试返回原始路径
            if is_udim:
                # 对于UDIM贴图，我们需要恢复原始的UDIM占位符
                original_path = full_path.replace('.1001.', udim_pattern)
                logger.info(f"文件不存在，返回原始UDIM路径: {original_path}")
                return original_path
            
            logger.info(f"文件不存在，返回原始路径: {full_path}")
            return full_path
    
    def normalize_path(self, path):
        """规范化路径，处理大小写和路径分隔符"""
        if not path:
            return None
            
        logger.info(f"正在规范化路径: {path}")
        
        # 规范化路径
        norm_path = os.path.normpath(path).replace('\\', '/')
        
        # 处理Windows盘符，确保使用大写
        if len(norm_path) > 1 and norm_path[1] == ':':
            drive = norm_path[0].upper()
            rest_path = norm_path[2:]
            norm_path = f"{drive}:{rest_path}"
            logger.info(f"处理Windows盘符: {path} -> {norm_path}")
            
        # 保留原始目录结构，包括aa/USD/
        # 注意：我们不再移除aa/USD/部分，因为这可能导致路径识别错误
        # 只进行基本的路径规范化，保留原始目录结构
        
        logger.info(f"规范化后的路径: {path} -> {norm_path}")
        return norm_path
    
    def extract_references_from_text(self, file_path):
        """从文本中提取引用路径"""
        references = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # 如果是二进制USD文件，直接返回空列表
            if not content or content.startswith(b'\x00') if isinstance(content, bytes) else content.startswith('\x00'):
                return references
        
            # 提取@开头的引用
            pattern = r'@([^@\s"\']+)'
            matches = re.findall(pattern, content)
            for path in matches:
                # 过滤掉不像是文件路径的内容
                if self.is_likely_usd_path(path) and not self.is_likely_texture_path(path):
                    references.append(path)
            
            # 提取引号中的引用
            patterns = [
                r'(?:prepend\s+references\s*=\s*@)([^@\s"\']+)(?:@)',  # prepend references = @path/to/texture.jpg@
                r'(?:append\s+references\s*=\s*@)([^@\s"\']+)(?:@)',   # append references = @path/to/texture.jpg@
                r'(?:references\s*=\s*@)([^@\s"\']+)(?:@)',            # references = @path/to/texture.jpg@
                r'(?:references\s*=\s*\[)([^\]]+)(?:\])',              # references = [...]
                r'(?:add\s+references\s*=\s*@)([^@\s"\']+)(?:@)',      # add references = @path/to/texture.jpg@
                r'(?:add\s+reference\s*=\s*@)([^@\s"\']+)(?:@)',       # add reference = @path/to/texture.jpg@
                r'(?:reference\s*=\s*@)([^@\s"\']+)(?:@)',             # reference = @path/to/texture.jpg@
                r'(?:assetInfo\s*=\s*{)([^}]+)(?:})',                  # assetInfo = {...}
                r'(?:payload\s*=\s*@)([^@\s"\']+)(?:@)',               # payload = @path/to/texture.jpg@
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if '[' in pattern:  # 处理引用列表
                        # 分割并清理引用列表中的路径
                        paths = re.findall(r'@([^@]+)@', match)
                        for path in paths:
                            path = path.strip()
                            if path and self.is_likely_usd_path(path) and not self.is_likely_texture_path(path):
                                references.append(path)
                    elif '{' in pattern:  # 处理assetInfo
                        # 提取assetInfo中的identifier
                        identifiers = re.findall(r'identifier\s*=\s*@([^@]+)@', match)
                        for identifier in identifiers:
                            if identifier and self.is_likely_usd_path(identifier) and not self.is_likely_texture_path(identifier):
                                references.append(identifier)
                    else:
                        # 直接添加匹配的路径
                        if match and self.is_likely_usd_path(match) and not self.is_likely_texture_path(match):
                            references.append(match)
                            
            # 同时将找到的贴图路径添加到纹理列表中
            texture_pattern = r'@([^@\s"\']+\.(?:jpg|jpeg|png|tif|tiff|exr|hdr|tx|tex|bmp|gif|psd|tga|iff|dpx|cin|svg))@'
            texture_matches = re.findall(texture_pattern, content)
            for path in texture_matches:
                if self.is_likely_texture_path(path):
                    # 获取当前USD文件名作为来源
                    usd_file_name = os.path.basename(file_path)
                    resolved_path = self.resolve_path(path, os.path.dirname(file_path))
                    if resolved_path:
                        self.add_texture_path(resolved_path, f"{usd_file_name}:texture_reference")
        except Exception as e:
            logger.error(f"从文件 {file_path} 中提取引用时出错: {str(e)}")
            logger.error(traceback.format_exc())
        
        return references
    
    def resolve_udim_sequence(self, file_path):
        """解析UDIM贴图序列，返回所有匹配的文件"""
        if not file_path:
            return []

        # 检查是否包含UDIM模式
        udim_patterns = ['<UDIM>', '<udim>', '1001', '.####.']
        has_udim = any(pattern in file_path for pattern in udim_patterns)

        if not has_udim:
            return [file_path]  # 不是UDIM序列，直接返回原路径

        # 获取文件目录
        file_dir = os.path.dirname(file_path)
        if not os.path.exists(file_dir):
            return [file_path]  # 目录不存在，返回原路径

        # 替换UDIM模式为通配符
        file_pattern = file_path

        # 处理不同格式的UDIM模式
        if '<UDIM>' in file_pattern:
            file_pattern = file_pattern.replace('<UDIM>', '[1-9][0-9][0-9][0-9]')
        elif '<udim>' in file_pattern:
            file_pattern = file_pattern.replace('<udim>', '[1-9][0-9][0-9][0-9]')

        # 处理.####.这种格式
        if '.####.' in file_pattern:
            file_pattern = file_pattern.replace('.####.', '.[1-9][0-9][0-9][0-9].')

        # 将路径中的[1-9][0-9][0-9][0-9]替换为*，用于glob匹配
        glob_pattern = file_pattern
        glob_pattern = re.sub(r'\[1-9\]\[0-9\]\[0-9\]\[0-9\]', '*', glob_pattern)

        # 使用glob查找所有匹配的文件
        matching_files = glob.glob(glob_pattern)

        # 如果没有找到匹配的文件，返回原路径
        if not matching_files:
            return [file_path]

        return matching_files
    
    def add_texture_path(self, path, source=None):
        """添加贴图路径到集合，处理UDIM序列"""
        if not path:
            return

        # 检查是否为UDIM贴图序列
        udim_count = 0
        is_udim = any(pattern in path for pattern in ['<UDIM>', '<udim>', '.####.', '.<udim>.', '.<UDIM>.'])
        
        if is_udim:
            # 尝试查找实际的UDIM贴图文件
            try:
                base_dir = os.path.dirname(path)
                file_name = os.path.basename(path)
                
                # 替换UDIM占位符为正则表达式模式
                if '<UDIM>' in file_name or '<udim>' in file_name:
                    pattern = file_name.replace('<UDIM>', r'\d{4}').replace('<udim>', r'\d{4}')
                elif '.####.' in file_name:
                    pattern = file_name.replace('.####.', r'.\d{4}.')
                else:
                    pattern = file_name
                
                # 查找匹配的文件
                if os.path.exists(base_dir):
                    for file in os.listdir(base_dir):
                        if re.match(pattern, file):
                            udim_count += 1
                
                logger.info(f"找到 {udim_count} 个UDIM贴图: {path}")
                # 保存UDIM贴图数量
                self.texture_udim_counts[path] = udim_count
            except Exception as e:
                logger.error(f"查找UDIM贴图时出错: {str(e)}")
        
        # 如果路径不在字典中，添加它
        if path not in self.texture_files:
            self.texture_files[path] = source
    
    def is_likely_texture_path(self, path):
        """判断路径是否可能是贴图路径"""
        if not path or not isinstance(path, str):
            return False
        
        # 清理路径
        path = path.strip().strip('"\'')
        
        # 检查文件扩展名
        texture_extensions = [
            '.jpg', '.jpeg', '.png', '.tif', '.tiff', '.exr', '.hdr', '.tx', '.tex',
            '.bmp', '.gif', '.psd', '.tga', '.iff', '.dpx', '.cin', '.svg'
        ]
        
        # 检查是否有任何一个扩展名匹配
        has_texture_ext = any(path.lower().endswith(ext) for ext in texture_extensions)
        
        # 检查是否包含UDIM占位符（注意大小写）
        udim_patterns = ['<UDIM>', '<udim>', '.####.', '.<udim>.', '.<UDIM>.', '1001.', '10[0-9][0-9]']
        has_udim = any(pattern in path for pattern in udim_patterns)
        
        # 检查路径中是否包含贴图相关的关键词
        texture_keywords = ['texture', 'map', 'image', 'tex', 'diffuse', 'albedo', 'normal', 'roughness', 'metallic',
                           'specular', 'emission', 'occlusion', 'height', 'bump', 'color', 'opacity', 'displacement']
        
        has_texture_keyword = any(keyword in path.lower() for keyword in texture_keywords)
        
        # 检查路径中是否包含常见的贴图目录名称
        texture_dir_keywords = ['texture', 'textures', 'tex', 'maps', 'images', 'txt', 'publish']
        has_texture_dir = any(f"/{keyword}/" in path.lower().replace('\\', '/') for keyword in texture_dir_keywords)
        
        # 如果有扩展名或UDIM占位符，则认为是贴图路径
        # 增加了对贴图目录的检查
        return has_texture_ext or has_udim or has_texture_dir or (has_texture_keyword and '.' in path)
    
    def is_likely_usd_path(self, path):
        """判断路径是否可能是USD文件路径
        
        Args:
            path: 路径字符串
            
        Returns:
            bool: 是否可能是USD文件路径
        """
        # 去除可能的引号
        path = path.strip('"\'')
        
        # 检查文件扩展名
        usd_extensions = ['.usd', '.usda', '.usdc', '.usdz']
        has_usd_ext = any(path.lower().endswith(ext) for ext in usd_extensions)
        
        # 检查是否包含常见的USD路径模式
        has_usd_pattern = any(pattern in path.lower() for pattern in ['/usd/', '/assets/', '/publish/', '/model/', '/lookdev/', '/animation/'])
        
        # 检查是否是相对路径或绝对路径
        looks_like_path = ('/' in path or '\\' in path) and not path.startswith('http')
        
        # 如果有USD扩展名，或者看起来像路径且包含USD路径模式，则认为是USD路径
        return has_usd_ext or (looks_like_path and has_usd_pattern)
    
    def scan_file_for_texture_paths(self, file_path, source_name=None):
        """直接扫描文件内容寻找可能的贴图路径"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # 查找常见的贴图定义模式
            file_patterns = [
                r'file\s*=\s*"([^"]+)"',  # file = "path/to/texture.jpg"
                r'sourceColorFile\s*=\s*"([^"]+)"',  # sourceColorFile = "path/to/texture.jpg"
                r'colorFile\s*=\s*"([^"]+)"',  # colorFile = "path/to/texture.jpg"
                r'texture:file\s*=\s*"([^"]+)"',  # texture:file = "path/to/texture.jpg"
                r'assetInfo:file\s*=\s*"([^"]+)"',  # assetInfo:file = "path/to/texture.jpg"
                r'inputs:file\s*=\s*"([^"]+)"',  # inputs:file = "path/to/texture.jpg"
                r'inputs:filename\s*=\s*"([^"]+)"',  # inputs:filename = "path/to/texture.jpg"
                r'asset inputs:file\s*=\s*@([^@]+)@',  # asset inputs:file = @path/to/texture.jpg@
                r'asset inputs:filename\s*=\s*@([^@]+)@',  # asset inputs:filename = @path/to/texture.jpg@
                r'asset inputs:[a-zA-Z0-9_]+_texture\s*=\s*@([^@]+)@',  # asset inputs:basecolor_texture = @path/to/texture.jpg@
                r'string inputs:file\s*=\s*"([^"]+)"',  # string inputs:file = "path/to/texture.jpg"
                r'string inputs:filename\s*=\s*"([^"]+)"',  # string inputs:filename = "path/to/texture.jpg"
            ]

            base_dir = os.path.dirname(file_path)
            
            # 如果没有提供来源名称，使用文件名
            if source_name is None:
                source_name = os.path.basename(file_path)

            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # MDL中的贴图定义模式
            texture_patterns = [
                r'texture_2d\s*"([^"]+)"',  # texture_2d "path/to/texture.jpg"
                r'tex::texture_2d\s*\(\s*"([^"]+)"\s*\)',  # tex::texture_2d("path/to/texture.jpg")
                r'file\s*=\s*"([^"]+)"',  # file = "path/to/texture.jpg"
            ]

            for pattern in texture_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if self.is_likely_texture_path(match):
                        resolved_path = self.resolve_path(match, base_dir)
                        if resolved_path:
                            self.add_texture_path(resolved_path, source_name)

        except Exception as e:
            logger.error(f"扫描文件 {file_path} 失败: {str(e)}")
            logger.error(traceback.format_exc())
    
    def extract_assets_from_usd(self, usd_file_path, base_dir=None):
        """从USD文件中提取所有资产"""
        # 如果已经处理过这个文件，则跳过
        abs_path = self.resolve_path(usd_file_path, base_dir)
        if not abs_path or abs_path in self.processed_assets:
            return

        self.processed_assets.add(abs_path)
        logger.info(f"正在处理USD文件: {abs_path}")

        # 获取文件所在目录作为基础目录
        current_dir = os.path.dirname(abs_path)
        
        # 如果提供了原始目录，优先使用它来解析相对路径
        effective_dir = base_dir if base_dir else current_dir
        logger.info(f"使用有效目录进行解析: {effective_dir}")
        
        # 获取当前处理的USD文件名，用作贴图来源
        current_usd_name = os.path.basename(abs_path)
        logger.info(f"当前处理的USD文件: {current_usd_name}")
        
        # 用于检查引用是否已经添加过
        def is_reference_already_added(ref_path):
            """检查引用是否已经添加过"""
            resolved_ref_path = self.resolve_path(ref_path, effective_dir)
            if not resolved_ref_path:
                return False
                
            for existing_ref, _ in self.references:
                existing_full_path = self.resolve_path(existing_ref, effective_dir)
                if existing_full_path and os.path.normpath(existing_full_path) == os.path.normpath(resolved_ref_path):
                    return True
            return False

        try:
            # 检查文件是否存在
            if not os.path.exists(abs_path):
                logger.error(f"文件不存在: {abs_path}")
                return
                
            # 检查文件扩展名
            file_ext = os.path.splitext(abs_path)[1].lower()
            logger.info(f"文件扩展名: {file_ext}")
            
            # 首先检查是否有shader文件夹，如果有，优先处理shader/main.usda
            shader_dir = os.path.join(os.path.dirname(abs_path), 'shader')
            has_shader_folder = os.path.exists(shader_dir) and os.path.isdir(shader_dir)
            
            logger.info(f"检查shader文件夹: {shader_dir}, 存在: {has_shader_folder}")
            
            if has_shader_folder:
                logger.info(f"发现shader文件夹: {shader_dir}")
                main_usda_path = os.path.join(shader_dir, 'main.usda')
                
                logger.info(f"检查main.usda文件: {main_usda_path}, 存在: {os.path.exists(main_usda_path)}")
                
                if os.path.exists(main_usda_path) and os.path.isfile(main_usda_path):
                    logger.info(f"发现shader/main.usda文件: {main_usda_path}")
                    
                    # 添加到引用列表，如果不存在的话
                    if not is_reference_already_added(main_usda_path):
                        self.references.append((main_usda_path, "shader"))
                    
                    # 清空当前的纹理列表，只使用shader/main.usda中的纹理
                    self.texture_files.clear()
                    logger.info("已清空纹理列表，将只使用shader/main.usda中的纹理")
                    
                    # 直接读取main.usda文件内容并提取所有@符号之间的内容
                    try:
                        with open(main_usda_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            
                        # 提取所有@符号之间的内容
                        pattern = r'@([^@]+)@'
                        matches = re.findall(pattern, content)
                        logger.info(f"从shader/main.usda中找到 {len(matches)} 个@符号之间的内容")
                        
                        for path in matches:
                            logger.info(f"@符号之间的内容: {path}")
                            # 检查是否是贴图路径
                            if '.' in path and any(ext in path.lower() for ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.exr', '.hdr']):
                                # 解析路径
                                resolved_path = self.resolve_path(path, shader_dir)
                                if resolved_path:
                                    # 检查是否包含UDIM相关字符
                                    if any(pattern in path for pattern in ['<UDIM>', '<udim>', '.####.', '.1001.']):
                                        self.add_texture_path(resolved_path, "shader:UDIM")
                                        logger.info(f"添加UDIM贴图: {resolved_path}")
                                    else:
                                        self.add_texture_path(resolved_path, "shader:texture")
                                        logger.info(f"添加普通贴图: {resolved_path}")
                            # 检查是否是USD文件引用
                            elif '.usda' in path.lower() or '.usd' in path.lower() or '.usdz' in path.lower():
                                # 解析路径
                                resolved_path = self.resolve_path(path, shader_dir)
                                if resolved_path:
                                    logger.info(f"从@符号中发现USD引用: {path} -> {resolved_path}")
                                    # 检查是否已经添加过这个引用
                                    ref_already_added = False
                                    for existing_ref, ref_type in self.references:
                                        existing_full_path = self.resolve_path(existing_ref, shader_dir)
                                        if existing_full_path and os.path.normpath(existing_full_path) == os.path.normpath(resolved_path):
                                            ref_already_added = True
                                            break
                                    
                                    if not ref_already_added:
                                        # 添加到references列表
                                        self.references.append((path, "reference"))
                                        # 递归处理引用的USD文件
                                        self.extract_assets_from_usd(resolved_path, shader_dir)
                    except Exception as e:
                        logger.error(f"处理shader/main.usda文件时出错: {str(e)}")
                        logger.error(traceback.format_exc())
                    
                    # 如果找到了纹理，则直接返回，不再处理其他文件
                    if self.texture_files:
                        logger.info(f"从shader/main.usda中找到了 {len(self.texture_files)} 个纹理，跳过其他处理")
                        logger.info(f"找到的纹理: {list(self.texture_files.keys())}")
                        return
                    else:
                        logger.info("从shader/main.usda中没有找到纹理，将继续处理其他文件")
            
            # 如果没有找到shader/main.usda或者没有从中提取到纹理，则继续处理主文件
            
            # 1. 从文本中提取引用
            text_references = self.extract_references_from_text(abs_path)
            if text_references:
                logger.info(f"从文本中发现 {len(text_references)} 个引用:")
                for ref in text_references:
                    logger.info(f"文本引用: {ref}")
                    # 使用有效目录解析相对路径
                    full_ref_path = self.resolve_path(ref, effective_dir)
                    if full_ref_path:
                        # 检查是否已经添加过这个引用
                        ref_already_added = False
                        for existing_ref, ref_type in self.references:
                            existing_full_path = self.resolve_path(existing_ref, effective_dir)
                            if existing_full_path and os.path.normpath(existing_full_path) == os.path.normpath(full_ref_path):
                                ref_already_added = True
                                break
                        
                        if not ref_already_added:
                            logger.info(f"添加新引用并递归处理: {full_ref_path}")
                            self.referenced_usd_files.add(full_ref_path)
                            # 添加到references列表
                            self.references.append((ref, "reference"))
                            # 递归处理引用的USD文件
                            self.extract_assets_from_usd(full_ref_path, effective_dir)
            
            # 2. 如果是USDA文件，直接从文件内容中提取@符号之间的内容
            if file_ext == '.usda':
                try:
                    with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                    # 提取所有@符号之间的内容
                    pattern = r'@([^@]+)@'
                    matches = re.findall(pattern, content)
                    logger.info(f"从{abs_path}中找到 {len(matches)} 个@符号之间的内容")
                    
                    for path in matches:
                        logger.info(f"@符号之间的内容: {path}")
                        # 检查是否是贴图路径
                        if '.' in path and any(ext in path.lower() for ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.exr', '.hdr']):
                            # 解析路径
                            resolved_path = self.resolve_path(path, effective_dir)
                            if resolved_path:
                                # 检查是否包含UDIM相关字符
                                if any(pattern in path for pattern in ['<UDIM>', '<udim>', '.####.', '.1001.']):
                                    self.add_texture_path(resolved_path, f"{current_usd_name}:UDIM")
                                    logger.info(f"添加UDIM贴图: {resolved_path}")
                                else:
                                    self.add_texture_path(resolved_path, f"{current_usd_name}:texture")
                                    logger.info(f"添加普通贴图: {resolved_path}")
                        # 检查是否是USD文件引用
                        elif '.usda' in path.lower() or '.usd' in path.lower() or '.usdz' in path.lower():
                            # 解析路径
                            resolved_path = self.resolve_path(path, effective_dir)
                            if resolved_path:
                                logger.info(f"从@符号中发现USD引用: {path} -> {resolved_path}")
                                # 检查是否已经添加过这个引用
                                ref_already_added = False
                                for existing_ref, ref_type in self.references:
                                    existing_full_path = self.resolve_path(existing_ref, effective_dir)
                                    if existing_full_path and os.path.normpath(existing_full_path) == os.path.normpath(resolved_path):
                                        ref_already_added = True
                                        break
                                
                                if not ref_already_added:
                                    # 添加到references列表
                                    self.references.append((path, "reference"))
                                    # 递归处理引用的USD文件
                                    self.extract_assets_from_usd(resolved_path, effective_dir)
                except Exception as e:
                    logger.error(f"处理USDA文件内容时出错: {str(e)}")
                    logger.error(traceback.format_exc())
            
            # 3. 使用USD API检查材质和着色器
            try:
                stage = Usd.Stage.Open(abs_path)
                if stage:
                    logger.info(f"成功打开USD舞台: {abs_path}")
                    
                    # 检查subLayers
                    layer_stack = stage.GetLayerStack()
                    for layer in layer_stack:
                        try:
                            # 尝试使用 identifier 属性
                            layer_path = layer.identifier
                            if layer_path != abs_path:  # 跳过当前文件
                                logger.info(f"发现subLayer: {layer_path}")
                                self.referenced_usd_files.add(layer_path)
                                # 添加到references列表
                                self.references.append((layer_path, "subLayer"))
                                # 递归处理subLayer
                                self.extract_assets_from_usd(layer_path, effective_dir)
                        except Exception as e:
                            logger.warning(f"获取层标识符失败: {str(e)}")
                    
                    # 遍历所有prim
                    for prim in stage.Traverse():
                        logger.info(f"处理Prim: {prim.GetPath()}, 类型: {prim.GetTypeName()}")
                        
                        # 检查引用和payload
                        if prim.HasReferences():
                            refs = prim.GetReferences()
                            for i in range(refs.GetNumReferences()):
                                try:
                                    ref = refs.GetReferencedLayer(i)
                                    if ref:
                                        ref_path = ref.identifier
                                        logger.info(f"在Prim {prim.GetPath()} 上发现引用: {ref_path}")
                                        self.referenced_usd_files.add(ref_path)
                                        # 添加到references列表
                                        self.references.append((ref_path, "reference"))
                                        # 递归处理引用
                                        self.extract_assets_from_usd(ref_path, effective_dir)
                                except Exception as e:
                                    logger.warning(f"处理引用失败: {str(e)}")
                        
                        if prim.HasPayloads():
                            payloads = prim.GetPayloads()
                            for i in range(payloads.GetNumPayloads()):
                                try:
                                    payload = payloads.GetPayloadAt(i)
                                    if payload.GetAssetPath():
                                        payload_path = payload.GetAssetPath()
                                        logger.info(f"在Prim {prim.GetPath()} 上发现payload: {payload_path}")
                                        self.referenced_usd_files.add(payload_path)
                                        # 添加到references列表
                                        self.references.append((payload_path, "payload"))
                                        # 递归处理payload
                                        resolved_payload_path = self.resolve_path(payload_path, effective_dir)
                                        if resolved_payload_path:
                                            self.extract_assets_from_usd(resolved_payload_path, effective_dir)
                                except Exception as e:
                                    logger.warning(f"处理payload失败: {str(e)}")
                        
                        # 检查材质
                        if UsdShade.Material(prim):
                            material = UsdShade.Material(prim)
                            logger.info(f"发现材质: {prim.GetPath()}")
                            self.collect_textures_from_material(material, effective_dir)
                        
                        # 检查着色器
                        elif UsdShade.Shader(prim):
                            shader = UsdShade.Shader(prim)
                            shader_name = prim.GetName()
                            
                            logger.info(f"发现着色器: {prim.GetPath()}")
                            self.examine_material_or_shader(prim, effective_dir)
            except Exception as e:
                logger.error(f"使用USD API处理文件时出错: {str(e)}")
                logger.error(traceback.format_exc())

        except Exception as e:
            logger.error(f"处理USD文件时出错: {str(e)}")
            logger.error(traceback.format_exc())
    
    def analyze_usd_file(self, file_path, original_dir=None):
        """分析USD文件，提取引用和贴图信息"""
        logger.info(f"开始分析USD文件: {file_path}")
        
        # 重置状态
        self.processed_assets = set()
        self.references = []
        self.texture_files = {}
        self.texture_udim_counts = {}  # 存储贴图的UDIM数量
        
        # 提取所有资产
        self.extract_assets_from_usd(file_path, original_dir)
        
        # 处理引用路径
        unique_references = []
        unique_paths = set()
        
        for ref_path, ref_type in self.references:
            # 解析路径
            resolved_path = self.resolve_path(ref_path, original_dir)
            if resolved_path:
                # 检查文件是否存在
                file_exists = os.path.exists(resolved_path)
                
                # 只添加存在的文件
                if file_exists:
                    # 规范化路径
                    norm_path = self.normalize_path(resolved_path)
                    
                    # 使用不区分大小写的比较来检查是否已经添加过
                    is_duplicate = False
                    for existing_path in unique_paths:
                        if norm_path.lower() == existing_path.lower():
                            is_duplicate = True
                            logger.info(f"跳过重复路径: {resolved_path} -> {norm_path}")
                            break
                    
                    if norm_path and not is_duplicate:
                        unique_paths.add(norm_path)
                        # 使用规范化后的路径
                        unique_references.append((norm_path, ref_type))
                        logger.info(f"添加规范化路径: {norm_path}, 类型: {ref_type}")
                else:
                    logger.info(f"跳过不存在的文件: {resolved_path}")
        
        self.references = unique_references
        
        # 处理纹理路径
        unique_textures = {}
        for tex_path, source in self.texture_files.items():
            resolved_path = self.resolve_path(tex_path, original_dir)
            if resolved_path:
                # 规范化路径
                norm_path = self.normalize_path(resolved_path)
                
                if norm_path:
                    # 检查贴图文件或目录是否存在
                    is_udim = any(pattern in norm_path for pattern in ['<UDIM>', '<udim>', '.####.', '.<udim>.', '.<UDIM>.'])
                    
                    if is_udim:
                        # 对于UDIM贴图，使用新的方法计算实际贴图数量
                        texture_count = self.count_udim_textures_in_path(norm_path)
                        if texture_count > 0:
                            unique_textures[norm_path] = source
                            # 保存UDIM贴图数量
                            self.texture_udim_counts[norm_path] = texture_count
                            logger.info(f"添加UDIM贴图: {norm_path}, 来源: {source}, 实际贴图数量: {texture_count}")
                        else:
                            logger.info(f"跳过无效的UDIM贴图(未找到匹配文件): {norm_path}")
                    else:
                        # 对于普通贴图，直接检查文件是否存在
                        if os.path.exists(norm_path):
                            unique_textures[norm_path] = source
                            # 计算目录中所有贴图的数量
                            texture_count = self.count_actual_textures(norm_path)
                            self.texture_udim_counts[norm_path] = texture_count
                            logger.info(f"添加普通贴图: {norm_path}, 来源: {source}, 实际贴图数量: {texture_count}")
                        else:
                            logger.info(f"跳过不存在的贴图: {norm_path}")
        
        self.texture_files = unique_textures
        
        # 构建结果
        result = {
            "references": [{"path": ref, "type": ref_type, "exists": os.path.exists(ref)} for ref, ref_type in self.references],
            "textures": [{"path": path, "source": source, "exists": True, "actual_texture_count": self.texture_udim_counts.get(path, 1)} for path, source in self.texture_files.items()],
            "texture_udim_counts": self.texture_udim_counts
        }
        
        logger.info(f"分析完成，找到 {len(self.references)} 个引用，{len(self.texture_files)} 个贴图")
        return result
    
    def collect_textures_from_material(self, material, base_dir):
        """从材质中收集贴图路径"""
        logger.info(f"收集材质 {material.GetPath()} 中的贴图")
        
        # 获取材质的所有输入
        for input in material.GetInputs():
            input_name = input.GetName().lower()
            logger.info(f"检查材质输入: {input_name}")
            self.collect_textures_from_input(input, base_dir, material.GetPrim().GetName())
        
        # 获取材质的所有输出
        for output in material.GetOutputs():
            output_name = output.GetName().lower()
            logger.info(f"检查材质输出: {output_name}")
            
            # 检查输出的连接
            if output.HasConnectedSource():
                source = output.GetConnectedSource()
                if source:
                    source_prim = source[0].GetPrim()
                    if UsdShade.Shader(source_prim):
                        shader = UsdShade.Shader(source_prim)
                        shader_name = shader.GetPrim().GetName()
                        logger.info(f"材质输出连接到着色器: {shader_name}")
                        
                        # 检查着色器的所有输入
                        for shader_input in shader.GetInputs():
                            self.collect_textures_from_input(shader_input, base_dir, shader_name)
    
    def examine_material_or_shader(self, prim, base_dir):
        """检查材质或着色器定义"""
        logger.info(f"检查材质或着色器: {prim.GetPath()}")
        
        # 如果是材质
        if UsdShade.Material(prim):
            material = UsdShade.Material(prim)
            self.collect_textures_from_material(material, base_dir)
            return
        
        # 如果是着色器
        if UsdShade.Shader(prim):
            shader = UsdShade.Shader(prim)
            shader_id = shader.GetShaderId()
            shader_name = prim.GetName()
            
            logger.info(f"着色器ID: {shader_id}, 名称: {shader_name}")
            
            # 特别处理UsdUVTexture
            if shader_id and "UsdUVTexture" in shader_id:
                logger.info(f"发现UsdUVTexture: {prim.GetPath()}")
                
                # 查找file输入
                file_input = shader.GetInput("file")
                if file_input:
                    texture_path = file_input.Get()
                    if texture_path and isinstance(texture_path, str):
                        resolved_path = self.resolve_path(texture_path, base_dir)
                        if resolved_path:
                            # 使用着色器名称作为来源
                            source = f"UsdUVTexture:{shader_name}"
                            logger.info(f"添加UsdUVTexture贴图: {resolved_path}, 来源: {source}")
                            self.add_texture_path(resolved_path, source)
            
            # 检查着色器的所有输入
            for input in shader.GetInputs():
                input_name = input.GetName().lower()
                logger.info(f"检查着色器输入: {input_name}")
                self.collect_textures_from_input(input, base_dir, shader_name)

    def collect_textures_from_input(self, input, base_dir, source_name=None):
        """从输入中收集贴图路径"""
        try:
            # 获取输入名称
            try:
                input_name = input.GetName().lower()
            except AttributeError:
                try:
                    input_name = input.GetAttr().GetName().lower()
                except:
                    input_name = "unknown_input"
                    logger.warning(f"无法获取输入名称，使用默认名称: {input_name}")
            
            # 如果没有提供来源名称，使用输入所在的prim名称
            if source_name is None:
                try:
                    source_name = input.GetAttr().GetPrim().GetName()
                except:
                    source_name = "unknown_source"
                    logger.warning(f"无法获取输入来源，使用默认来源: {source_name}")
            
            # 检查输入名称是否与贴图相关
            texture_related = any(tex_key in input_name.lower() for tex_key in
                                ["texture", "file", "map", "image", "tex", "diffuse", "albedo", "normal", "roughness", "metallic",
                                "specular", "emission", "occlusion", "height", "bump", "color", "opacity", "displacement"])
            
            # 检查输入的连接
            if input.HasConnectedSource():
                source = input.GetConnectedSource()
                if source:
                    source_prim = source[0].GetPrim()
                    if UsdShade.Shader(source_prim):
                        shader = UsdShade.Shader(source_prim)
                        shader_name = shader.GetPrim().GetName()
                        logger.info(f"发现连接到着色器: {shader_name}")
                        
                        # 检查着色器的所有输入
                        for shader_input in shader.GetInputs():
                            self.collect_textures_from_input(shader_input, base_dir, shader_name)
        except Exception as e:
            logger.error(f"处理输入连接时出错: {str(e)}")
            logger.error(traceback.format_exc())
    
    def scan_mdl_file_for_textures(self, mdl_path, source_name=None):
        """扫描MDL文件中的贴图引用"""
        try:
            if not os.path.exists(mdl_path):
                return

            base_dir = os.path.dirname(mdl_path)
            
            # 如果没有提供来源名称，使用文件名
            if source_name is None:
                source_name = os.path.basename(mdl_path)

            with open(mdl_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # MDL中的贴图定义模式
            texture_patterns = [
                r'texture_2d\s*"([^"]+)"',  # texture_2d "path/to/texture.jpg"
                r'tex::texture_2d\s*\(\s*"([^"]+)"\s*\)',  # tex::texture_2d("path/to/texture.jpg")
                r'file\s*=\s*"([^"]+)"',  # file = "path/to/texture.jpg"
            ]

            for pattern in texture_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if self.is_likely_texture_path(match):
                        resolved_path = self.resolve_path(match, base_dir)
                        if resolved_path:
                            self.add_texture_path(resolved_path, source_name)

        except Exception as e:
            logger.error(f"扫描文件 {mdl_path} 失败: {str(e)}")
            logger.error(traceback.format_exc())
    
    def extract_textures_from_usda(self, file_path, base_dir=None):
        """从USDA文件中提取纹理路径"""
        logger.info(f"从USDA文件中提取纹理: {file_path}")
        logger.info(f"基础目录: {base_dir}")
        
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                logger.error(f"USDA文件不存在: {file_path}")
                return
                
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 记录文件内容的前100个字符，用于调试
            logger.info(f"文件内容前100个字符: {content[:100]}")
            logger.info(f"文件内容长度: {len(content)} 字符")
            
            # 提取纹理路径的模式
            # 1. asset inputs:texture_name = @path@
            texture_pattern1 = r'asset\s+inputs:([a-zA-Z0-9_]+)\s*=\s*@([^@]+)@'
            # 2. asset inputs:texture_name:file = @path@
            texture_pattern2 = r'asset\s+inputs:([a-zA-Z0-9_]+):file\s*=\s*@([^@]+)@'
            # 3. filename = @path@
            texture_pattern3 = r'filename\s*=\s*@([^@]+)@'
            # 4. file = @path@
            texture_pattern4 = r'file\s*=\s*@([^@]+)@'
            # 5. 其他可能的模式
            texture_pattern5 = r'texture\s*=\s*@([^@]+)@'
            texture_pattern6 = r'colorMap\s*=\s*@([^@]+)@'
            # 7. 通用的 asset 属性模式
            texture_pattern7 = r'asset\s+([a-zA-Z0-9_:]+)\s*=\s*@([^@]+)@'
            # 8. inputs:*_texture 模式 (特别针对您提供的USDA文件格式)
            texture_pattern8 = r'inputs:([a-zA-Z0-9_]+)_texture\s*=\s*@([^@]+)@'
            # 9. 查找 inputs:file 模式 (特别针对您提供的USDA文件格式)
            texture_pattern9 = r'inputs:file\s*=\s*@([^@]+)@'
            # 10. 在 @ 符号之间的 UDIM 路径 (针对您提供的USDA文件格式)
            texture_pattern10 = r'@([^@]*(?:<UDIM>|<udim>|\.####\.|\.1001\.|\.10[0-9][0-9]\.|\.udim\.|\.UDIM\.)[^@]*)@'
            
            # 记录所有找到的纹理路径
            all_textures = []
            
            # 1. 查找 asset inputs:texture_name = @path@ 模式
            matches1 = re.findall(texture_pattern1, content)
            logger.info(f"模式1找到 {len(matches1)} 个匹配")
            for input_name, path in matches1:
                logger.info(f"模式1匹配: input={input_name}, path={path}")
                if self.is_likely_texture_path(path):
                    resolved_path = self.resolve_path(path, base_dir)
                    if resolved_path:
                        context = os.path.basename(file_path)
                        self.add_texture_path(resolved_path, f"{context}:{input_name}")
                        all_textures.append((resolved_path, input_name))
            
            # 2. 查找 asset inputs:texture_name:file = @path@ 模式
            matches2 = re.findall(texture_pattern2, content)
            logger.info(f"模式2找到 {len(matches2)} 个匹配")
            for input_name, path in matches2:
                logger.info(f"模式2匹配: input={input_name}, path={path}")
                if self.is_likely_texture_path(path):
                    resolved_path = self.resolve_path(path, base_dir)
                    if resolved_path:
                        context = os.path.basename(file_path)
                        self.add_texture_path(resolved_path, f"{context}:{input_name}")
                        all_textures.append((resolved_path, input_name))
            
            # 3. 查找 filename = @path@ 模式
            matches3 = re.findall(texture_pattern3, content)
            logger.info(f"模式3找到 {len(matches3)} 个匹配")
            for path in matches3:
                logger.info(f"模式3匹配: path={path}")
                if self.is_likely_texture_path(path):
                    resolved_path = self.resolve_path(path, base_dir)
                    if resolved_path:
                        context = os.path.basename(file_path)
                        self.add_texture_path(resolved_path, f"{context}:filename")
                        all_textures.append((resolved_path, "filename"))
            
            # 4. 查找 file = @path@ 模式
            matches4 = re.findall(texture_pattern4, content)
            logger.info(f"模式4找到 {len(matches4)} 个匹配")
            for path in matches4:
                logger.info(f"模式4匹配: path={path}")
                if self.is_likely_texture_path(path):
                    resolved_path = self.resolve_path(path, base_dir)
                    if resolved_path:
                        context = os.path.basename(file_path)
                        self.add_texture_path(resolved_path, f"{context}:file")
                        all_textures.append((resolved_path, "file"))
            
            # 5. 查找其他可能的模式
            matches5 = re.findall(texture_pattern5, content)
            logger.info(f"模式5找到 {len(matches5)} 个匹配")
            for path in matches5:
                logger.info(f"模式5匹配: path={path}")
                if self.is_likely_texture_path(path):
                    resolved_path = self.resolve_path(path, base_dir)
                    if resolved_path:
                        context = os.path.basename(file_path)
                        self.add_texture_path(resolved_path, f"{context}:texture")
                        all_textures.append((resolved_path, "texture"))
            
            matches6 = re.findall(texture_pattern6, content)
            logger.info(f"模式6找到 {len(matches6)} 个匹配")
            for path in matches6:
                logger.info(f"模式6匹配: path={path}")
                if self.is_likely_texture_path(path):
                    resolved_path = self.resolve_path(path, base_dir)
                    if resolved_path:
                        context = os.path.basename(file_path)
                        self.add_texture_path(resolved_path, f"{context}:colorMap")
                        all_textures.append((resolved_path, "colorMap"))
                        
            # 7. 查找通用的 asset 属性模式
            matches7 = re.findall(texture_pattern7, content)
            logger.info(f"模式7找到 {len(matches7)} 个匹配")
            for attr_name, path in matches7:
                logger.info(f"模式7匹配: attr={attr_name}, path={path}")
                if self.is_likely_texture_path(path):
                    resolved_path = self.resolve_path(path, base_dir)
                    if resolved_path:
                        context = os.path.basename(file_path)
                        self.add_texture_path(resolved_path, f"{context}:{attr_name}")
                        all_textures.append((resolved_path, attr_name))
            
            # 8. inputs:*_texture 模式 (特别针对您提供的USDA文件格式)
            matches8 = re.findall(texture_pattern8, content)
            logger.info(f"模式8找到 {len(matches8)} 个匹配")
            for input_name, path in matches8:
                logger.info(f"模式8匹配: input={input_name}, path={path}")
                if self.is_likely_texture_path(path):
                    resolved_path = self.resolve_path(path, base_dir)
                    if resolved_path:
                        context = os.path.basename(file_path)
                        self.add_texture_path(resolved_path, f"{context}:{input_name}")
                        all_textures.append((resolved_path, input_name))
                    
            # 9. 查找 inputs:file 模式 (特别针对您提供的USDA文件格式)
            matches9 = re.findall(texture_pattern9, content)
            logger.info(f"模式9找到 {len(matches9)} 个匹配")
            for path in matches9:
                logger.info(f"模式9匹配: path={path}")
                if self.is_likely_texture_path(path):
                    resolved_path = self.resolve_path(path, base_dir)
                    if resolved_path:
                        context = os.path.basename(file_path)
                        self.add_texture_path(resolved_path, f"{context}:file")
                        all_textures.append((resolved_path, "file"))
            
            # 10. 在 @ 符号之间的 UDIM 路径 (针对您提供的USDA文件格式)
            matches10 = re.findall(texture_pattern10, content)
            logger.info(f"模式10找到 {len(matches10)} 个匹配")
            for path in matches10:
                logger.info(f"模式10匹配: path={path}")
                if self.is_likely_texture_path(path):
                    resolved_path = self.resolve_path(path, base_dir)
                    if resolved_path:
                        context = os.path.basename(file_path)
                        self.add_texture_path(resolved_path, f"{context}:UDIM")
                        all_textures.append((resolved_path, "UDIM"))
            
            # 11. 直接提取所有 @ 符号之间的内容（最通用的方法）
            all_at_pattern = r'@([^@]+)@'
            all_at_matches = re.findall(all_at_pattern, content)
            logger.info(f"提取所有@符号之间的内容，找到 {len(all_at_matches)} 个匹配")
            for path in all_at_matches:
                logger.info(f"@符号之间的内容: {path}")
                # 解析路径
                resolved_path = self.resolve_path(path, base_dir)
                if resolved_path:
                    context = os.path.basename(file_path)
                    
                    # 检查是否是USD文件引用
                    if '.usda' in path.lower() or '.usd' in path.lower() or '.usdz' in path.lower():
                        logger.info(f"从@符号中发现USD引用: {path} -> {resolved_path}")
                        # 检查是否已经添加过这个引用
                        ref_already_added = False
                        for existing_ref, ref_type in self.references:
                            existing_full_path = self.resolve_path(existing_ref, base_dir)
                            if existing_full_path and os.path.normpath(existing_full_path) == os.path.normpath(resolved_path):
                                ref_already_added = True
                                break
                        
                        if not ref_already_added:
                            # 添加到references列表
                            self.references.append((path, "reference"))
                            # 递归处理引用的USD文件
                            self.extract_assets_from_usd(resolved_path, base_dir)
                    # 检查是否是贴图路径
                    elif any(ext in path.lower() for ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.exr', '.hdr']):
                        # 检查是否包含 UDIM 相关字符
                        if any(pattern in path for pattern in ['<UDIM>', '<udim>', '.####.', '.<udim>.', '.<UDIM>.']):
                            logger.info(f"发现UDIM路径: {path} -> {resolved_path}")
                            self.add_texture_path(resolved_path, f"{context}:UDIM")
                        else:
                            logger.info(f"发现普通路径: {path} -> {resolved_path}")
                            self.add_texture_path(resolved_path, f"{context}:asset")
                        all_textures.append((resolved_path, "asset"))
            
            # 查找所有引号内的路径，可能是纹理路径
            # 这是一个更通用的方法，可能会有更多的误报，所以放在最后
            path_pattern = r'"([^"]+\.(jpg|jpeg|png|tif|tiff|exr|hdr|tx|tex|bmp|gif|psd|tga|iff|dpx|cin|svg))"'
            path_matches = re.findall(path_pattern, content, re.IGNORECASE)
            logger.info(f"通用路径模式找到 {len(path_matches)} 个匹配")
            
            for path, ext in path_matches:
                # 检查是否已经添加过
                already_added = False
                for added_path, _ in all_textures:
                    if os.path.normpath(path) == os.path.normpath(added_path):
                        already_added = True
                        break
                
                if not already_added and self.is_likely_texture_path(path):
                    logger.info(f"通用路径匹配: path={path}")
                    resolved_path = self.resolve_path(path, base_dir)
                    if resolved_path:
                        context = os.path.basename(file_path)
                        self.add_texture_path(resolved_path, f"{context}:generic")
                        all_textures.append((resolved_path, "generic"))
            
            # 特别处理 UDIM 纹理 - 增强版
            # 1. 标准 UDIM 格式
            udim_pattern1 = r'"([^"]*(?:<UDIM>|<udim>)[^"]*)"'
            # 2. 数字格式 UDIM
            udim_pattern2 = r'"([^"]*(?:\.####\.|\.1001\.|\.10[0-9][0-9]\.)[^"]*)"'
            # 3. 文本 udim 格式
            udim_pattern3 = r'"([^"]*(?:\.udim\.|\.UDIM\.)[^"]*)"'
            # 4. 任何包含 udim 的路径
            udim_pattern4 = r'"([^"]*udim[^"]*\.(jpg|jpeg|png|tif|tiff|exr|hdr|tx|tex))"'
            
            # 合并所有 UDIM 模式的结果
            udim_matches = []
            for pattern in [udim_pattern1, udim_pattern2, udim_pattern3, udim_pattern4]:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if isinstance(matches[0], tuple) if matches else False:
                    # 如果匹配结果是元组（带有扩展名的情况），只取路径部分
                    matches = [m[0] for m in matches]
                udim_matches.extend(matches)
            
            logger.info(f"UDIM模式找到 {len(udim_matches)} 个匹配: {udim_matches}")
            
            for path in udim_matches:
                # 检查是否已经添加过
                already_added = False
                for added_path, _ in all_textures:
                    if os.path.normpath(path) == os.path.normpath(added_path):
                        already_added = True
                        break
                
                if not already_added:
                    logger.info(f"UDIM路径匹配: path={path}")
                    resolved_path = self.resolve_path(path, base_dir)
                    if resolved_path:
                        context = os.path.basename(file_path)
                        self.add_texture_path(resolved_path, f"{context}:UDIM")
                        all_textures.append((resolved_path, "UDIM"))
            
            # 记录找到的纹理总数
            logger.info(f"从USDA文件中提取的纹理总数: {len(self.texture_files)}")
            
        except Exception as e:
            logger.error(f"从USDA文件中提取纹理时出错: {str(e)}")
            logger.error(traceback.format_exc())

    def extract_assets_from_usd(self, usd_file_path, base_dir=None):
        """从USD文件中提取所有资产"""
        # 如果已经处理过这个文件，则跳过
        abs_path = self.resolve_path(usd_file_path, base_dir)
        if not abs_path or abs_path in self.processed_assets:
            return

        self.processed_assets.add(abs_path)
        logger.info(f"正在处理USD文件: {abs_path}")

        # 获取文件所在目录作为基础目录
        current_dir = os.path.dirname(abs_path)
        
        # 如果提供了原始目录，优先使用它来解析相对路径
        effective_dir = base_dir if base_dir else current_dir
        logger.info(f"使用有效目录进行解析: {effective_dir}")
        
        # 获取当前处理的USD文件名，用作贴图来源
        current_usd_name = os.path.basename(abs_path)
        logger.info(f"当前处理的USD文件: {current_usd_name}")
        
        # 用于检查引用是否已经添加过
        def is_reference_already_added(ref_path):
            """检查引用是否已经添加过"""
            resolved_ref_path = self.resolve_path(ref_path, effective_dir)
            if not resolved_ref_path:
                return False
                
            for existing_ref, _ in self.references:
                existing_full_path = self.resolve_path(existing_ref, effective_dir)
                if existing_full_path and os.path.normpath(existing_full_path) == os.path.normpath(resolved_ref_path):
                    return True
            return False

        try:
            # 检查文件是否存在
            if not os.path.exists(abs_path):
                logger.error(f"文件不存在: {abs_path}")
                return
                
            # 检查文件扩展名
            file_ext = os.path.splitext(abs_path)[1].lower()
            logger.info(f"文件扩展名: {file_ext}")
            
            # 首先检查是否有shader文件夹，如果有，优先处理shader/main.usda
            shader_dir = os.path.join(os.path.dirname(abs_path), 'shader')
            has_shader_folder = os.path.exists(shader_dir) and os.path.isdir(shader_dir)
            
            logger.info(f"检查shader文件夹: {shader_dir}, 存在: {has_shader_folder}")
            
            if has_shader_folder:
                logger.info(f"发现shader文件夹: {shader_dir}")
                main_usda_path = os.path.join(shader_dir, 'main.usda')
                
                logger.info(f"检查main.usda文件: {main_usda_path}, 存在: {os.path.exists(main_usda_path)}")
                
                if os.path.exists(main_usda_path) and os.path.isfile(main_usda_path):
                    logger.info(f"发现shader/main.usda文件: {main_usda_path}")
                    
                    # 添加到引用列表，如果不存在的话
                    if not is_reference_already_added(main_usda_path):
                        self.references.append((main_usda_path, "shader"))
                    
                    # 清空当前的纹理列表，只使用shader/main.usda中的纹理
                    self.texture_files.clear()
                    logger.info("已清空纹理列表，将只使用shader/main.usda中的纹理")
                    
                    # 直接读取main.usda文件内容并提取所有@符号之间的内容
                    try:
                        with open(main_usda_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            
                        # 提取所有@符号之间的内容
                        pattern = r'@([^@]+)@'
                        matches = re.findall(pattern, content)
                        logger.info(f"从shader/main.usda中找到 {len(matches)} 个@符号之间的内容")
                        
                        for path in matches:
                            logger.info(f"@符号之间的内容: {path}")
                            # 检查是否是贴图路径
                            if '.' in path and any(ext in path.lower() for ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.exr', '.hdr']):
                                # 解析路径
                                resolved_path = self.resolve_path(path, shader_dir)
                                if resolved_path:
                                    # 检查是否包含UDIM相关字符
                                    if any(pattern in path for pattern in ['<UDIM>', '<udim>', '.####.', '.1001.']):
                                        self.add_texture_path(resolved_path, "shader:UDIM")
                                        logger.info(f"添加UDIM贴图: {resolved_path}")
                                    else:
                                        self.add_texture_path(resolved_path, "shader:texture")
                                        logger.info(f"添加普通贴图: {resolved_path}")
                            # 检查是否是USD文件引用
                            elif '.usda' in path.lower() or '.usd' in path.lower() or '.usdz' in path.lower():
                                # 解析路径
                                resolved_path = self.resolve_path(path, shader_dir)
                                if resolved_path:
                                    logger.info(f"从@符号中发现USD引用: {path} -> {resolved_path}")
                                    # 检查是否已经添加过这个引用
                                    ref_already_added = False
                                    for existing_ref, ref_type in self.references:
                                        existing_full_path = self.resolve_path(existing_ref, shader_dir)
                                        if existing_full_path and os.path.normpath(existing_full_path) == os.path.normpath(resolved_path):
                                            ref_already_added = True
                                            break
                                    
                                    if not ref_already_added:
                                        # 添加到references列表
                                        self.references.append((path, "reference"))
                                        # 递归处理引用的USD文件
                                        self.extract_assets_from_usd(resolved_path, shader_dir)
                    except Exception as e:
                        logger.error(f"处理shader/main.usda文件时出错: {str(e)}")
                        logger.error(traceback.format_exc())
                    
                    # 如果找到了纹理，则直接返回，不再处理其他文件
                    if self.texture_files:
                        logger.info(f"从shader/main.usda中找到了 {len(self.texture_files)} 个纹理，跳过其他处理")
                        logger.info(f"找到的纹理: {list(self.texture_files.keys())}")
                        return
                    else:
                        logger.info("从shader/main.usda中没有找到纹理，将继续处理其他文件")
            
            # 如果没有找到shader/main.usda或者没有从中提取到纹理，则继续处理主文件
            
            # 1. 从文本中提取引用
            text_references = self.extract_references_from_text(abs_path)
            if text_references:
                logger.info(f"从文本中发现 {len(text_references)} 个引用:")
                for ref in text_references:
                    logger.info(f"文本引用: {ref}")
                    # 使用有效目录解析相对路径
                    full_ref_path = self.resolve_path(ref, effective_dir)
                    if full_ref_path:
                        # 检查是否已经添加过这个引用
                        ref_already_added = False
                        for existing_ref, ref_type in self.references:
                            existing_full_path = self.resolve_path(existing_ref, effective_dir)
                            if existing_full_path and os.path.normpath(existing_full_path) == os.path.normpath(full_ref_path):
                                ref_already_added = True
                                break
                        
                        if not ref_already_added:
                            logger.info(f"添加新引用并递归处理: {full_ref_path}")
                            self.referenced_usd_files.add(full_ref_path)
                            # 添加到references列表
                            self.references.append((ref, "reference"))
                            # 递归处理引用的USD文件
                            self.extract_assets_from_usd(full_ref_path, effective_dir)
            
            # 2. 如果是USDA文件，直接从文件内容中提取@符号之间的内容
            if file_ext == '.usda':
                try:
                    with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        
                    # 提取所有@符号之间的内容
                    pattern = r'@([^@]+)@'
                    matches = re.findall(pattern, content)
                    logger.info(f"从{abs_path}中找到 {len(matches)} 个@符号之间的内容")
                    
                    for path in matches:
                        logger.info(f"@符号之间的内容: {path}")
                        # 检查是否是贴图路径
                        if '.' in path and any(ext in path.lower() for ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.exr', '.hdr']):
                            # 解析路径
                            resolved_path = self.resolve_path(path, effective_dir)
                            if resolved_path:
                                # 检查是否包含UDIM相关字符
                                if any(pattern in path for pattern in ['<UDIM>', '<udim>', '.####.', '.1001.']):
                                    self.add_texture_path(resolved_path, f"{current_usd_name}:UDIM")
                                    logger.info(f"添加UDIM贴图: {resolved_path}")
                                else:
                                    self.add_texture_path(resolved_path, f"{current_usd_name}:texture")
                                    logger.info(f"添加普通贴图: {resolved_path}")
                        # 检查是否是USD文件引用
                        elif '.usda' in path.lower() or '.usd' in path.lower() or '.usdz' in path.lower():
                            # 解析路径
                            resolved_path = self.resolve_path(path, effective_dir)
                            if resolved_path:
                                logger.info(f"从@符号中发现USD引用: {path} -> {resolved_path}")
                                # 检查是否已经添加过这个引用
                                ref_already_added = False
                                for existing_ref, ref_type in self.references:
                                    existing_full_path = self.resolve_path(existing_ref, effective_dir)
                                    if existing_full_path and os.path.normpath(existing_full_path) == os.path.normpath(resolved_path):
                                        ref_already_added = True
                                        break
                                
                                if not ref_already_added:
                                    # 添加到references列表
                                    self.references.append((path, "reference"))
                                    # 递归处理引用的USD文件
                                    self.extract_assets_from_usd(resolved_path, effective_dir)
                except Exception as e:
                    logger.error(f"处理USDA文件内容时出错: {str(e)}")
                    logger.error(traceback.format_exc())
            
            # 3. 使用USD API检查材质和着色器
            try:
                stage = Usd.Stage.Open(abs_path)
                if stage:
                    logger.info(f"成功打开USD舞台: {abs_path}")
                    
                    # 检查subLayers
                    layer_stack = stage.GetLayerStack()
                    for layer in layer_stack:
                        try:
                            # 尝试使用 identifier 属性
                            layer_path = layer.identifier
                            if layer_path != abs_path:  # 跳过当前文件
                                logger.info(f"发现subLayer: {layer_path}")
                                self.referenced_usd_files.add(layer_path)
                                # 添加到references列表
                                self.references.append((layer_path, "subLayer"))
                                # 递归处理subLayer
                                self.extract_assets_from_usd(layer_path, effective_dir)
                        except Exception as e:
                            logger.warning(f"获取层标识符失败: {str(e)}")
                    
                    # 遍历所有prim
                    for prim in stage.Traverse():
                        logger.info(f"处理Prim: {prim.GetPath()}, 类型: {prim.GetTypeName()}")
                        
                        # 检查引用和payload
                        if prim.HasReferences():
                            refs = prim.GetReferences()
                            for i in range(refs.GetNumReferences()):
                                try:
                                    ref = refs.GetReferencedLayer(i)
                                    if ref:
                                        ref_path = ref.identifier
                                        logger.info(f"在Prim {prim.GetPath()} 上发现引用: {ref_path}")
                                        self.referenced_usd_files.add(ref_path)
                                        # 添加到references列表
                                        self.references.append((ref_path, "reference"))
                                        # 递归处理引用
                                        self.extract_assets_from_usd(ref_path, effective_dir)
                                except Exception as e:
                                    logger.warning(f"处理引用失败: {str(e)}")
                        
                        if prim.HasPayloads():
                            payloads = prim.GetPayloads()
                            for i in range(payloads.GetNumPayloads()):
                                try:
                                    payload = payloads.GetPayloadAt(i)
                                    if payload.GetAssetPath():
                                        payload_path = payload.GetAssetPath()
                                        logger.info(f"在Prim {prim.GetPath()} 上发现payload: {payload_path}")
                                        self.referenced_usd_files.add(payload_path)
                                        # 添加到references列表
                                        self.references.append((payload_path, "payload"))
                                        # 递归处理payload
                                        resolved_payload_path = self.resolve_path(payload_path, effective_dir)
                                        if resolved_payload_path:
                                            self.extract_assets_from_usd(resolved_payload_path, effective_dir)
                                except Exception as e:
                                    logger.warning(f"处理payload失败: {str(e)}")
                        
                        # 检查材质
                        if UsdShade.Material(prim):
                            material = UsdShade.Material(prim)
                            logger.info(f"发现材质: {prim.GetPath()}")
                            self.collect_textures_from_material(material, effective_dir)
                        
                        # 检查着色器
                        elif UsdShade.Shader(prim):
                            shader = UsdShade.Shader(prim)
                            shader_name = prim.GetName()
                            
                            logger.info(f"发现着色器: {prim.GetPath()}")
                            self.examine_material_or_shader(prim, effective_dir)
            except Exception as e:
                logger.error(f"使用USD API处理文件时出错: {str(e)}")
                logger.error(traceback.format_exc())

        except Exception as e:
            logger.error(f"处理USD文件时出错: {str(e)}")
            logger.error(traceback.format_exc())

    def count_actual_textures(self, base_path):
        """计算实际路径下的所有贴图数量，特别处理 UDIM 贴图"""
        if not base_path or not isinstance(base_path, str):
            return 0
            
        # 将路径标准化但保持原始大小写
        path = base_path.replace('\\', '/')
        logger.info(f"开始计算贴图数量，路径: {path}")
        
        # 提取基础目录
        dir_path = os.path.dirname(path)
        file_name = os.path.basename(path)
        
        # 检查目录是否存在
        if not os.path.exists(dir_path):
            logger.warning(f"贴图目录不存在: {dir_path}")
            return 0
        
        # 检查是否是 UDIM 贴图
        is_udim = any(pattern in path for pattern in ['<UDIM>', '<udim>', '.####.', '.<udim>.', '.<UDIM>.'])
        
        # 如果是 UDIM 贴图，提取基础名称
        if is_udim:
            base_name = None
            extension = None
            
            # 提取基础名称和扩展名
            for pattern in ['<UDIM>', '<udim>', '.####.', '.<udim>.', '.<UDIM>.']:
                if pattern in file_name:
                    parts = file_name.split(pattern)
                    if len(parts) >= 2:
                        base_name = parts[0]
                        extension = parts[1]
                        break
            
            if base_name and extension:
                logger.info(f"UDIM 贴图基础名称: {base_name}, 扩展名: {extension}")
                
                # 尝试多种模式来匹配 UDIM 贴图
                patterns = [
                    # 标准 UDIM 格式: base.1001.ext, base.1002.ext 等
                    re.compile(f"^{re.escape(base_name)}\\.(\\d{{4}})\\.{re.escape(extension)}$"),
                    # 简单数字格式: base.1.ext, base.2.ext 等
                    re.compile(f"^{re.escape(base_name)}\\.(\\d+)\\.{re.escape(extension)}$"),
                    # 其他可能的格式
                    re.compile(f"^{re.escape(base_name)}.*\\.{re.escape(extension)}$")
                ]
                
                # 计算匹配的文件数量
                count = 0
                matched_files = []
                
                for file in os.listdir(dir_path):
                    for pattern in patterns:
                        if pattern.match(file):
                            count += 1
                            matched_files.append(file)
                            logger.info(f"找到 UDIM 贴图: {os.path.join(dir_path, file)}")
                            break
                
                if count > 0:
                    logger.info(f"目录 {dir_path} 中共有 {count} 个 UDIM 贴图: {matched_files}")
                    return count
                else:
                    logger.warning(f"未找到匹配的 UDIM 贴图，将计算目录中所有贴图的数量")
        
        # 如果不是 UDIM 贴图或者没有找到匹配的 UDIM 贴图，计算所有贴图的数量
        try:
            count = 0
            matched_files = []
            
            for file in os.listdir(dir_path):
                # 检查文件是否是图像文件
                ext = os.path.splitext(file)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.exr', '.hdr', '.tx', '.tex']:
                    count += 1
                    matched_files.append(file)
                    logger.info(f"找到贴图: {os.path.join(dir_path, file)}")
            
            logger.info(f"目录 {dir_path} 中共有 {count} 个贴图: {matched_files}")
            return count
        except Exception as e:
            logger.error(f"计算实际贴图数量时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return 0

    def count_udim_textures_in_path(self, udim_path):
        """
        解析 "图片名字.<UDIM>.图片格式" 这样的格式，并计算实际路径下所有同名贴图的数量
        
        Args:
            udim_path: UDIM 贴图路径，例如 "E:/path/to/texture.<UDIM>.jpg"
            
        Returns:
            int: 实际路径下同名贴图的数量
        """
        if not udim_path or not isinstance(udim_path, str):
            return 0
            
        # 标准化路径
        path = udim_path.replace('\\', '/')
        logger.info(f"解析 UDIM 贴图路径: {path}")
        
        # 提取目录和文件名
        dir_path = os.path.dirname(path)
        file_name = os.path.basename(path)
        
        # 检查目录是否存在
        if not os.path.exists(dir_path):
            logger.warning(f"UDIM 贴图目录不存在: {dir_path}")
            return 0
            
        # 检查是否是 UDIM 贴图路径
        udim_patterns = ['<UDIM>', '<udim>', '.####.', '.<udim>.', '.<UDIM>.']
        is_udim = any(pattern in file_name for pattern in udim_patterns)
        
        if not is_udim:
            logger.warning(f"不是 UDIM 贴图路径: {path}")
            return 0
            
        # 提取基础名称和扩展名
        base_name = None
        extension = None
        pattern_found = None
        
        for pattern in udim_patterns:
            if pattern in file_name:
                parts = file_name.split(pattern)
                if len(parts) >= 2:
                    base_name = parts[0]
                    extension = parts[1]
                    pattern_found = pattern
                    break
        
        if not base_name or not extension:
            logger.warning(f"无法从 UDIM 贴图路径提取基础名称和扩展名: {path}")
            return 0
            
        logger.info(f"UDIM 贴图基础名称: {base_name}, 扩展名: {extension}")
        
        # 构建正则表达式模式
        patterns = []
        
        # 根据找到的模式类型构建不同的正则表达式
        if pattern_found in ['<UDIM>', '<udim>']:
            # 对于 <UDIM> 或 <udim> 格式，查找 base.1001.ext, base.1002.ext 等
            patterns.append(re.compile(f"^{re.escape(base_name)}(\d{{4}}){re.escape(extension)}$"))
        elif pattern_found in ['.####.', '.<udim>.', '.<UDIM>.']:
            # 对于 .####. 或 .<udim>. 或 .<UDIM>. 格式，查找 base.1001.ext, base.1002.ext 等
            patterns.append(re.compile(f"^{re.escape(base_name)}\.(\d{{4}})\.{re.escape(extension)}$"))
        
        # 添加简单数字格式作为备选
        patterns.append(re.compile(f"^{re.escape(base_name)}\.(\d+)\.{re.escape(extension)}$"))
        patterns.append(re.compile(f"^{re.escape(base_name)}(\d+){re.escape(extension)}$"))
        
        # 查找匹配的文件
        matched_files = []
        
        try:
            for file in os.listdir(dir_path):
                for pattern in patterns:
                    if pattern.match(file):
                        matched_files.append(file)
                        logger.info(f"找到匹配的 UDIM 贴图: {os.path.join(dir_path, file)}")
                        break
        except Exception as e:
            logger.error(f"查找 UDIM 贴图时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return 0
            
        count = len(matched_files)
        logger.info(f"UDIM 贴图 {path} 共找到 {count} 个实际文件: {matched_files}")
        
        # 如果没有找到匹配文件但路径中包含 UDIM 占位符，尝试直接检查文件是否存在
        if count == 0 and is_udim:
            # 尝试替换 <UDIM> 为通配符并使用 glob 查找文件
            wildcard_path = path
            for udim_pattern in ['<UDIM>', '<udim>']:
                if udim_pattern in wildcard_path:
                    # 对于 E:/filmserver/test/library/prop/bb/main/txt/publish/v001/bb/<UDIM>.jpg 格式
                    wildcard_path = wildcard_path.replace(udim_pattern, '*')
            
            for pattern_format in ['.####.', '.<udim>.', '.<UDIM>.']:
                if pattern_format in wildcard_path:
                    # 对于 base.####.ext 或 base.<udim>.ext 或 base.<UDIM>.ext 格式
                    wildcard_path = wildcard_path.replace(pattern_format, '.*.')
            
            import glob
            matched_glob_files = glob.glob(wildcard_path)
            count = len(matched_glob_files)
            logger.info(f"使用通配符 {wildcard_path} 找到 {count} 个文件: {matched_glob_files}")
        
        return count

    def extract_assets_from_mdl(self, file_path, source_name=None):
        """从MDL文件中提取贴图路径"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            file_patterns = [
                r'file\s*=\s*"([^"]+)"',  # file = "path/to/texture.jpg"
                r'sourceColorFile\s*=\s*"([^"]+)"',  # sourceColorFile = "path/to/texture.jpg"
                r'colorFile\s*=\s*"([^"]+)"',  # colorFile = "path/to/texture.jpg"
                r'texture:file\s*=\s*"([^"]+)"',  # texture:file = "path/to/texture.jpg"
                r'assetInfo:file\s*=\s*"([^"]+)"',  # assetInfo:file = "path/to/texture.jpg"
                r'inputs:file\s*=\s*"([^"]+)"',  # inputs:file = "path/to/texture.jpg"
                r'inputs:filename\s*=\s*"([^"]+)"',  # inputs:filename = "path/to/texture.jpg"
                r'asset inputs:file\s*=\s*@([^@]+)@',  # asset inputs:file = @path/to/texture.jpg@
                r'asset inputs:filename\s*=\s*@([^@]+)@',  # asset inputs:filename = @path/to/texture.jpg@
                r'asset inputs:[a-zA-Z0-9_]+_texture\s*=\s*@([^@]+)@',  # asset inputs:basecolor_texture = @path/to/texture.jpg@
                r'string inputs:file\s*=\s*"([^"]+)"',  # string inputs:file = "path/to/texture.jpg"
                r'string inputs:filename\s*=\s*"([^"]+)"',  # string inputs:filename = "path/to/texture.jpg"
            ]

            base_dir = os.path.dirname(file_path)
            
            # 如果没有提供来源名称，使用文件名
            if source_name is None:
                source_name = os.path.basename(file_path)
            
            # 尝试从文件内容中提取prim名称
            prim_pattern = r'def\s+"([^"]+)"\s*\('
            prim_matches = re.findall(prim_pattern, content)
            current_prim = None
            
            # 分析文件内容，按行处理
            lines = content.split('\n')
            current_prim = None
            in_prim_block = False
            brace_count = 0
            
            # 当前材质或着色器的名称
            current_material = None
            current_shader = None
            
            for line in lines:
                # 检查是否开始一个新的prim定义
                prim_match = re.search(r'def\s+"?([^"\s]+)"?\s*\(', line)
                if prim_match:
                    current_prim = prim_match.group(1)
                    in_prim_block = True
                    brace_count = 0
                    # 检查这一行是否有左花括号
                    if '{' in line:
                        brace_count += 1
                    continue
                
                # 检查是否定义了材质
                material_match = re.search(r'def\s+Material\s+"?([^"\s]+)"?\s*\(', line)
                if material_match:
                    current_material = material_match.group(1)
                    logger.info(f"发现材质定义: {current_material}")
                    continue
                
                # 检查是否定义了着色器
                shader_match = re.search(r'def\s+Shader\s+"?([^"\s]+)"?\s*\(', line)
                if shader_match:
                    current_shader = shader_match.group(1)
                    logger.info(f"发现着色器定义: {current_shader}")
                    continue
                
                # 跟踪花括号以确定prim块的范围
                if in_prim_block:
                    brace_count += line.count('{') - line.count('}')
                    if brace_count <= 0:
                        in_prim_block = False
                        current_prim = None
                
                # 在当前prim块内查找贴图
                if in_prim_block:
                    # 确定当前上下文（材质或着色器）
                    context = current_shader if current_shader else current_material
                    if not context:
                        context = current_prim
                    
                    # 查找贴图路径
                    for pattern in file_patterns:
                        matches = re.findall(pattern, line)
                        for match in matches:
                            if self.is_likely_texture_path(match):
                                resolved_path = self.resolve_path(match, base_dir)
                                if resolved_path:
                                    # 使用当前上下文作为贴图来源
                                    logger.info(f"在 '{context}' 中发现贴图: {resolved_path}")
                                    self.add_texture_path(resolved_path, f"{source_name}:{context}")
                    
                    # 特别处理asset inputs:*_texture类型的属性
                    asset_texture_match = re.search(r'asset\s+inputs:([a-zA-Z0-9_]+)_texture\s*=\s*@([^@]+)@', line)
                    if asset_texture_match:
                        input_name = asset_texture_match.group(1)
                        texture_path = asset_texture_match.group(2)
                        if self.is_likely_texture_path(texture_path):
                            resolved_path = self.resolve_path(texture_path, base_dir)
                            if resolved_path:
                                logger.info(f"在 '{context}' 中发现 {input_name} 贴图: {resolved_path}")
                                self.add_texture_path(resolved_path, f"{source_name}:{context}:{input_name}")

        except Exception as e:
            logger.error(f"扫描文件 {file_path} 失败: {str(e)}")
            logger.error(traceback.format_exc())
