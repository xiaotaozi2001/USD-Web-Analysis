import os
import shutil
import tempfile
import logging
import traceback
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, UploadFile, HTTPException, Form, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pathlib import Path
from pxr import Usd, UsdGeom, Sdf, UsdShade, Ar
from usd_analyzer import EnhancedUsdAnalyzer

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,  # 改为 DEBUG 级别以获取更多信息
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 创建临时目录
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_uploads")
os.makedirs(TEMP_DIR, exist_ok=True)
logger.info(f"Created temp directory at: {TEMP_DIR}")

# 创建增强型USD分析器实例
enhanced_analyzer = EnhancedUsdAnalyzer()

app = FastAPI()

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API模型定义
class FileItem(BaseModel):
    name: str
    path: str
    is_directory: bool
    size: Optional[int] = None

class TextureItem(BaseModel):
    path: str
    source: str
    exists: Optional[bool] = True
    type: Optional[str] = None
    udim_count: Optional[int] = None
    actual_texture_count: Optional[int] = None

class ReferenceItem(BaseModel):
    path: str
    type: str
    prim_path: str

class PackageRequest(BaseModel):
    file_path: str
    output_path: str
    textures: List[Dict[str, Any]]
    references: List[Dict[str, Any]]

@app.get("/browse_directory")
async def browse_directory(directory_path: str = ""):
    """浏览指定目录下的文件和子目录"""
    try:
        # 如果目录路径为空，则使用系统根目录
        if not directory_path:
            # 在Windows上列出所有驱动器
            if os.name == 'nt':
                import string
                from ctypes import windll
                drives = []
                bitmask = windll.kernel32.GetLogicalDrives()
                for letter in string.ascii_uppercase:
                    if bitmask & 1:
                        drives.append(letter + ":\\")
                    bitmask >>= 1

                return {
                    "current_path": "",
                    "parent_path": None,
                    "items": [
                        FileItem(
                            name=drive,
                            path=drive,
                            is_directory=True,
                            size=None
                        ) for drive in drives
                    ]
                }
            else:
                # 在Unix系统上使用根目录
                directory_path = "/"

        # 确保目录路径存在
        if not os.path.exists(directory_path):
            raise HTTPException(status_code=404, detail=f"目录不存在: {directory_path}")

        if not os.path.isdir(directory_path):
            raise HTTPException(status_code=400, detail=f"路径不是一个目录: {directory_path}")

        # 获取父目录路径
        parent_path = os.path.dirname(directory_path) if directory_path != os.path.dirname(directory_path) else None

        # 列出目录内容
        items = []
        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)
            is_dir = os.path.isdir(item_path)

            # 只包含目录和USD文件
            if is_dir or item.lower().endswith(('.usd', '.usda', '.usdc')):
                items.append(
                    FileItem(
                        name=item,
                        path=item_path,
                        is_directory=is_dir,
                        size=None if is_dir else os.path.getsize(item_path)
                    )
                )

        # 按照目录在前，文件在后的顺序排序
        items.sort(key=lambda x: (not x.is_directory, x.name.lower()))

        return {
            "current_path": directory_path,
            "parent_path": parent_path,
            "items": items
        }

    except Exception as e:
        logging.error(f"浏览目录错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"浏览目录错误: {str(e)}")

@app.post("/analyze")
async def analyze_file(file: UploadFile, file_path: str = Form(None), is_drag_drop: str = Form(None)):
    temp_file_path = None
    try:
        # 保存上传的文件
        temp_file_path = os.path.join(TEMP_DIR, file.filename)
        logger.info(f"Saving file to: {temp_file_path}")

        try:
            with open(temp_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            logger.info(f"Successfully saved file to: {temp_file_path}")

            # 记录原始文件路径（如果提供）
            original_file_path = file_path
            original_dir = None

            # 检查是否是拖拽文件
            is_drag_drop_file = is_drag_drop == 'true'
            logger.info(f"Is drag and drop file: {is_drag_drop_file}")

            # 如果是拖拽文件，尝试查找原始文件
            if is_drag_drop_file:
                logger.info("Attempting to find original file for drag and drop")

                # 尝试在常见目录中查找文件
                common_dirs = [
                    r"E:\filmserver\test\library\prop\all\main\lookdev\workarea\usd",
                    r"E:\filmserver\test\library\prop",
                    r"E:\filmserver\test\library\env",
                    r"E:\filmserver\test\library",
                    r"E:\filmserver\test",
                    r"E:\filmserver"
                ]

                for common_dir in common_dirs:
                    if os.path.exists(common_dir):
                        logger.info(f"Searching in common directory: {common_dir}")

                        # 使用os.walk遍历目录树
                        for root, dirs, files in os.walk(common_dir):
                            if file.filename in files:
                                found_path = os.path.join(root, file.filename)
                                logger.info(f"Found original file: {found_path}")

                                # 比较文件大小，确认是否是同一个文件
                                temp_size = os.path.getsize(temp_file_path)
                                found_size = os.path.getsize(found_path)

                                if temp_size == found_size:
                                    logger.info(f"File sizes match: {temp_size} bytes")
                                    original_file_path = found_path
                                    original_dir = os.path.dirname(found_path)
                                    break
                                else:
                                    logger.info(f"File sizes don't match: temp={temp_size}, found={found_size}")

                        if original_file_path:
                            break

            if original_file_path:
                logger.info(f"Original file path provided or found: {original_file_path}")
                original_dir = os.path.dirname(original_file_path)

                # 检查原始目录是否存在
                if os.path.exists(original_dir):
                    logger.info(f"Original directory exists: {original_dir}")
                else:
                    logger.warning(f"Original directory does not exist: {original_dir}")
                    # 尝试创建目录结构以便测试
                    try:
                        os.makedirs(original_dir, exist_ok=True)
                        logger.info(f"Created original directory: {original_dir}")
                    except Exception as e:
                        logger.warning(f"Could not create original directory: {str(e)}")
            else:
                logger.info("No original file path provided or found")

            # 如果找到了原始文件，直接分析原始文件
            file_to_analyze = original_file_path if original_file_path and os.path.exists(original_file_path) else temp_file_path
            logger.info(f"Analyzing file: {file_to_analyze}")

            # 使用增强型分析器分析USD文件，传入原始目录信息
            result = enhanced_analyzer.analyze_usd_file(file_to_analyze, original_dir)
            logger.info(f"Analysis result: {result}")
            logger.info(f"Texture list length: {len(result.get('textures', []))}")
            logger.info(f"Texture list content: {result.get('textures', [])}")

            response_data = {
                "filename": file.filename,
                "original_path": original_file_path,
                "analysis": {
                    "success": True,
                    "references": result["references"],
                    "textures": result.get("textures", []),
                    "texture_udim_counts": result.get("texture_udim_counts", {})
                }
            }
            logger.info(f"Analysis complete for file: {file.filename}")
            logger.debug(f"Response data: {response_data}")
            return response_data

        except Exception as e:
            logger.error(f"Error analyzing file: {str(e)}\n{traceback.format_exc()}")
            return {
                "filename": file.filename,
                "original_path": original_file_path,
                "analysis": {
                    "success": False,
                    "error": str(e)
                }
            }
    finally:
        # 清理临时文件
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                # 保留文件用于调试
                # os.remove(temp_file_path)
                pass
            except Exception as e:
                logger.error(f"Error removing temp file: {str(e)}")

@app.post("/analyze_path")
async def analyze_file_path(file_path: str = Form(...)):
    try:
        # Record original file path
        logger.info(f"Received file path: {file_path}")

        # Normalize file path, handle possible path format issues
        clean_path = file_path.strip()
        logger.info(f"Cleaned path: {clean_path}")

        # 保存原始路径用于错误报告
        original_path = clean_path

        # 检查是否是相对路径
        if not os.path.isabs(clean_path):
            logger.info(f"处理相对路径: {clean_path}")
            # 尝试转换为绝对路径
            abs_path = os.path.abspath(clean_path)
            logger.info(f"转换为绝对路径: {abs_path}")
            if os.path.exists(abs_path):
                clean_path = abs_path
                logger.info(f"成功转换为绝对路径: {clean_path}")

        # Try different path formats
        if not os.path.exists(clean_path):
            # Try replacing path separators
            alt_path1 = clean_path.replace('\\', '/')
            alt_path2 = clean_path.replace('/', '\\')

            logger.info(f"Trying alternative path 1: {alt_path1}")
            logger.info(f"Trying alternative path 2: {alt_path2}")

            if os.path.exists(alt_path1):
                clean_path = alt_path1
                logger.info(f"Successfully used alternative path 1")
            elif os.path.exists(alt_path2):
                clean_path = alt_path2
                logger.info(f"Successfully used alternative path 2")

        # 如果仍然找不到文件，尝试在常见目录中查找
        if not os.path.exists(clean_path):
            logger.info(f"在常见目录中查找文件: {os.path.basename(clean_path)}")

            # 尝试在常见目录中查找文件
            common_dirs = [
                r"E:\filmserver\test\library\prop\all\main\lookdev\workarea\usd",
                r"E:\filmserver\test\library\prop\all\main\lookdev\publish\v001",
                r"E:\filmserver\test\library\env\test\aa\lookdev\publish\v001",
                r"E:\filmserver\test\library\prop",
                r"E:\filmserver\test\library\env",
                r"E:\filmserver\test\library",
                r"E:\filmserver\test",
                r"E:\filmserver",
                r"E:\Project\USD_Web_Analysis\backend\temp_uploads"
            ]

            filename = os.path.basename(clean_path)
            for common_dir in common_dirs:
                if os.path.exists(common_dir):
                    test_path = os.path.join(common_dir, filename)
                    logger.info(f"尝试路径: {test_path}")
                    if os.path.exists(test_path):
                        clean_path = test_path
                        logger.info(f"在常见目录中找到文件: {clean_path}")
                        break

        # Check if file exists
        if not os.path.exists(clean_path):
            logger.error(f"File does not exist: {clean_path} (original: {original_path})")
            return {
                "filename": os.path.basename(clean_path),
                "analysis": {
                    "success": False,
                    "error": f"File does not exist: {clean_path}"
                }
            }

        logger.info(f"Directly analyzing file path: {clean_path}")

        # Get the original directory for resolving relative paths
        original_dir = os.path.dirname(clean_path)
        logger.info(f"Original directory: {original_dir}")

        # Reset analyzer state
        enhanced_analyzer.reset()

        # Use enhanced analyzer to analyze USD file, passing original directory info
        result = enhanced_analyzer.analyze_usd_file(clean_path, original_dir)
        logger.info(f"Analysis result: {result}")
        logger.info(f"Texture list length: {len(result.get('textures', []))}")

        # Add more detailed log output
        if result.get('textures'):
            logger.info(f"First 5 texture items: {result.get('textures', [])[:5]}")
            if result.get('textures'):
                logger.info(f"Keys of first texture item: {list(result.get('textures', [])[0].keys()) if result.get('textures') else 'None'}")
                logger.info(f"Values of first texture item: {result.get('textures', [])[0] if result.get('textures') else 'None'}")
        else:
            logger.warning("Texture list is empty")

        response_data = {
            "filename": os.path.basename(clean_path),
            "original_path": clean_path,
            "analysis": {
                "success": True,
                "references": result["references"],
                "textures": result.get("textures", [])
            }
        }

        # Log complete response data
        logger.info(f"Response data: {response_data}")

        return response_data

    except Exception as e:
        logger.error(f"Error analyzing file: {str(e)}\n{traceback.format_exc()}")
        return {
            "filename": os.path.basename(file_path) if file_path else "Unknown file",
            "analysis": {
                "success": False,
                "error": str(e)
            }
        }

@app.get("/analyze_file_path")
async def analyze_file_path(file_path: str):
    """分析指定路径的USD文件"""
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}

        # 检查文件扩展名
        _, ext = os.path.splitext(file_path)
        if ext.lower() not in ['.usd', '.usda', '.usdc', '.usdz']:
            return {"success": False, "error": f"不支持的文件类型: {ext}"}

        # 分析USD文件
        analyzer = EnhancedUsdAnalyzer()
        result = analyzer.analyze_usd_file(file_path)

        # 构建响应
        response = {
            "success": True,
            "references": result["references"],
            "textures": [
                {
                    "path": texture["path"],
                    "source": texture["source"],
                    "exists": texture.get("exists", True),
                    "type": "UDIM" if "<UDIM>" in texture["path"] or "<udim>" in texture["path"] else "regular",
                    "actual_texture_count": texture.get("actual_texture_count", result.get("texture_udim_counts", {}).get(texture["path"], 1))
                }
                for texture in result["textures"]
            ],
            "texture_udim_counts": result.get("texture_udim_counts", {})
        }

        return response
    except Exception as e:
        logger.error(f"分析文件失败: {str(e)}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": f"分析文件失败: {str(e)}"}

@app.post("/package")
async def package_files(request: PackageRequest):
    """将分析出的USD文件和贴图打包到指定路径"""
    try:
        # 打印请求信息以便调试
        logger.info(f"收到打包请求: file_path={request.file_path}, output_path={request.output_path}")

        # 检查输入文件是否存在
        if not os.path.exists(request.file_path):
            logger.error(f"源文件不存在: {request.file_path}")
            # 尝试解决可能的路径问题
            normalized_path = request.file_path.replace('\\', '/')
            if os.path.exists(normalized_path):
                logger.info(f"使用规范化路径成功: {normalized_path}")
                request.file_path = normalized_path
            else:
                # 尝试其他可能的路径格式
                alternative_path = request.file_path.replace('/', '\\')
                if os.path.exists(alternative_path):
                    logger.info(f"使用替代路径成功: {alternative_path}")
                    request.file_path = alternative_path
                else:
                    return {"success": False, "message": f"源文件不存在: {request.file_path}\n已尝试路径: {normalized_path}, {alternative_path}"}

        # 检查输出路径是否存在，如果不存在则创建
        output_path = request.output_path
        if not os.path.exists(output_path):
            os.makedirs(output_path, exist_ok=True)
            logger.info(f"创建输出目录: {output_path}")

        # 复制主USD文件
        source_file = request.file_path
        file_name = os.path.basename(source_file)

        # 提取相对路径部分
        # 假设文件路径格式为 E:/filmserver/test/library/prop/bb/main/USD/lookdev/main.usda
        # 我们需要提取 test/library/prop/bb/main/USD/lookdev/main.usda 部分
        path_parts = source_file.replace('\\', '/').split('/')
        if 'filmserver' in path_parts:
            # 找到filmserver的索引
            filmserver_index = path_parts.index('filmserver')
            if filmserver_index + 1 < len(path_parts):
                relative_path = '/'.join(path_parts[filmserver_index+1:])
            else:
                relative_path = file_name
        else:
            # 如果找不到filmserver，则使用完整的文件名
            relative_path = file_name

        # 创建目标文件路径
        target_file = os.path.join(output_path, relative_path)
        target_dir = os.path.dirname(target_file)

        # 确保目标目录存在
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        # 复制主USD文件
        shutil.copy2(source_file, target_file)
        logger.info(f"复制主USD文件: {source_file} -> {target_file}")

        # 复制引用的USD文件 - 严格按照分析结果一比一复制，保留完整路径结构
        copied_references = []
        for ref in request.references:
            ref_path = ref.get('path')
            ref_type = ref.get('type', 'reference')
            if not ref_path:
                logger.warning(f"引用路径为空，跳过")
                continue

            # 检查文件是否存在，记录详细信息
            if not os.path.exists(ref_path):
                logger.warning(f"引用文件不存在: {ref_path}，类型: {ref_type}，跳过")
                continue

            logger.info(f"处理引用文件: {ref_path}, 类型: {ref_type}")

            # 提取相对路径 - 保持原始目录结构，包括aa/USD/部分
            ref_path_parts = ref_path.replace('\\', '/').split('/')

            # 处理不同类型的路径
            if 'filmserver' in ref_path_parts:
                # 如果路径包含filmserver，以filmserver后的部分作为相对路径
                ref_server_index = ref_path_parts.index('filmserver')
                if ref_server_index + 1 < len(ref_path_parts):
                    ref_relative_path = '/'.join(ref_path_parts[ref_server_index+1:])
                else:
                    ref_relative_path = os.path.basename(ref_path)
                logger.info(f"从filmserver路径提取: {ref_path} -> {ref_relative_path}")
            else:
                # 尝试多种方法来确定合适的相对路径
                source_dir = os.path.dirname(source_file).replace('\\', '/')
                ref_dir = os.path.dirname(ref_path).replace('\\', '/')

                # 方法1: 如果引用文件在源文件的子目录中，保持相对结构
                if ref_dir.startswith(source_dir):
                    ref_relative_path = ref_path.replace(source_dir, '').lstrip('/')
                    logger.info(f"使用源文件子目录相对路径: {ref_path} -> {ref_relative_path}")
                else:
                    # 方法2: 查找关键目录标识符
                    key_folders = ['USD', 'usd', 'assets', 'scenes', 'shots', 'env', 'aa']
                    found_key_folder = False

                    for key_folder in key_folders:
                        if key_folder in ref_path_parts:
                            # 从关键文件夹开始保留路径结构
                            key_index = ref_path_parts.index(key_folder)
                            ref_relative_path = '/'.join(ref_path_parts[key_index:])
                            logger.info(f"使用关键目录标识符相对路径: {ref_path} -> {ref_relative_path}")
                            found_key_folder = True
                            break

                    # 方法3: 如果前两种方法都不适用，使用父目录+文件名
                    if not found_key_folder:
                        parent_dir = os.path.basename(os.path.dirname(ref_path))
                        ref_relative_path = os.path.join(parent_dir, os.path.basename(ref_path))
                        logger.info(f"使用父目录+文件名相对路径: {ref_path} -> {ref_relative_path}")

            # 创建目标引用文件路径
            ref_target_file = os.path.join(output_path, ref_relative_path)
            ref_target_dir = os.path.dirname(ref_target_file)

            # 确保目标目录存在
            if not os.path.exists(ref_target_dir):
                os.makedirs(ref_target_dir, exist_ok=True)
                logger.info(f"创建目录: {ref_target_dir}")

            # 复制引用文件
            try:
                shutil.copy2(ref_path, ref_target_file)
                copied_references.append({
                    "source": ref_path,
                    "target": ref_target_file,
                    "type": ref_type
                })
                logger.info(f"成功复制引用文件: {ref_path} -> {ref_target_file}")
            except Exception as e:
                logger.error(f"复制引用文件失败: {ref_path} -> {ref_target_file}, 错误: {str(e)}")
                logger.error(traceback.format_exc())

        # 复制贴图文件 - 严格按照分析结果一比一复制，增强对UDIM贴图的支持
        copied_textures = []
        for texture in request.textures:
            texture_path = texture.get('path')
            if not texture_path:
                logger.warning(f"贴图路径为空，跳过")
                continue

            # 获取贴图的额外信息
            texture_source = texture.get('source', '')
            texture_type = texture.get('type', '')
            is_udim_from_analysis = any(pattern in texture_path for pattern in ['<UDIM>', '<udim>', '.####.', '.<UDIM>.', '.<udim>.'])
            udim_count = texture.get('udim_count', 0)
            actual_texture_count = texture.get('actual_texture_count', 0)

            logger.info(f"处理贴图: {texture_path}, 来源: {texture_source}, 类型: {texture_type}, UDIM: {is_udim_from_analysis}, 实际贴图数: {actual_texture_count}")

            # 检查是否是UDIM贴图 - 支持更多的UDIM模式
            is_udim = False
            udim_pattern = None
            udim_placeholder = None

            # 支持多种UDIM模式
            if "<UDIM>" in texture_path:
                is_udim = True
                udim_placeholder = "<UDIM>"
                udim_pattern = texture_path.replace("<UDIM>", "*")
            elif "<udim>" in texture_path:
                is_udim = True
                udim_placeholder = "<udim>"
                udim_pattern = texture_path.replace("<udim>", "*")
            elif ".####." in texture_path:
                is_udim = True
                udim_placeholder = ".####."
                udim_pattern = texture_path.replace(".####.", ".*.")  # 使用通配符匹配UDIM数字
            elif ".<UDIM>." in texture_path:
                is_udim = True
                udim_placeholder = ".<UDIM>."
                udim_pattern = texture_path.replace(".<UDIM>.", ".*.")
            elif ".<udim>." in texture_path:
                is_udim = True
                udim_placeholder = ".<udim>."
                udim_pattern = texture_path.replace(".<udim>.", ".*.")

            if is_udim and udim_pattern:
                # 对于UDIM贴图，需要查找所有匹配的文件
                udim_dir = os.path.dirname(texture_path)
                if not os.path.exists(udim_dir):
                    logger.warning(f"UDIM贴图目录不存在: {udim_dir}，跳过")
                    continue

                # 获取文件名部分（不含路径）
                udim_basename = os.path.basename(udim_pattern)
                # 在目录中查找所有匹配的文件
                import glob
                import re

                # 使用更精确的匹配模式
                matching_files = glob.glob(os.path.join(udim_dir, udim_basename))

                # 验证匹配的文件确实是UDIM序列
                verified_udim_files = []

                # 提取基本文件名（不含UDIM数字）
                base_filename = os.path.basename(texture_path)
                if udim_placeholder:
                    # 替换UDIM占位符为正则表达式模式
                    if udim_placeholder in ["<UDIM>", "<udim>"]:
                        base_pattern = base_filename.replace(udim_placeholder, r"(\d{4})")
                    elif udim_placeholder == ".####.":
                        base_pattern = base_filename.replace(udim_placeholder, r"\.(\d{4})\.")
                    elif udim_placeholder in [".<UDIM>.", ".<udim>."]:
                        base_pattern = base_filename.replace(udim_placeholder, r"\.(\d{4})\.")
                    else:
                        # 默认模式
                        base_pattern = base_filename.replace(udim_placeholder, r"(\d{4})")

                    # 编译正则表达式
                    pattern = re.compile(base_pattern)

                    # 验证每个匹配的文件
                    for file_path in matching_files:
                        file_name = os.path.basename(file_path)
                        match = pattern.match(file_name)
                        if match and 1000 <= int(match.group(1)) <= 1999:  # UDIM范围通常是1001-1999
                            verified_udim_files.append(file_path)
                            logger.info(f"验证UDIM贴图: {file_path}, UDIM索引: {match.group(1)}")

                # 如果没有验证通过的UDIM文件，尝试使用原始匹配结果
                if not verified_udim_files and matching_files:
                    logger.warning(f"未能验证UDIM序列，使用所有匹配文件: {matching_files}")
                    verified_udim_files = matching_files

                if not verified_udim_files:
                    logger.warning(f"未找到匹配的UDIM贴图: {os.path.join(udim_dir, udim_basename)}，跳过")
                    continue

                logger.info(f"找到 {len(verified_udim_files)} 个匹配的UDIM贴图: {verified_udim_files}")

                # 使用验证过的UDIM文件列表进行复制
                for matching_file in verified_udim_files:
                    if os.path.isfile(matching_file):
                        # 提取相对路径 - 保持原始目录结构
                        tex_path_parts = matching_file.replace('\\', '/').split('/')

                        # 处理不同类型的路径
                        if 'filmserver' in tex_path_parts:
                            # 如果路径包含filmserver，以filmserver后的部分作为相对路径
                            tex_server_index = tex_path_parts.index('filmserver')
                            if tex_server_index + 1 < len(tex_path_parts):
                                tex_relative_path = '/'.join(tex_path_parts[tex_server_index+1:])
                            else:
                                tex_relative_path = os.path.basename(matching_file)
                            logger.info(f"从filmserver路径提取贴图路径: {matching_file} -> {tex_relative_path}")
                        else:
                            # 尝试多种方法来确定合适的相对路径
                            source_dir = os.path.dirname(source_file).replace('\\', '/')
                            tex_dir = os.path.dirname(matching_file).replace('\\', '/')

                            # 方法1: 如果贴图文件在源文件的子目录中，保持相对结构
                            if tex_dir.startswith(source_dir):
                                tex_relative_path = matching_file.replace(source_dir, '').lstrip('/')
                                logger.info(f"使用源文件子目录相对路径(贴图): {matching_file} -> {tex_relative_path}")
                            else:
                                # 方法2: 查找关键目录标识符
                                key_folders = ['texture', 'textures', 'tex', 'maps', 'images', 'txt', 'publish', 'USD', 'usd', 'assets']
                                found_key_folder = False

                                tex_dir_parts = tex_dir.split('/')
                                for key_folder in key_folders:
                                    if key_folder in tex_dir_parts:
                                        # 从关键文件夹开始保留路径结构
                                        key_index = tex_dir_parts.index(key_folder)
                                        tex_relative_path = '/'.join(tex_dir_parts[key_index:] + [os.path.basename(matching_file)])
                                        logger.info(f"使用关键目录标识符相对路径(贴图): {matching_file} -> {tex_relative_path}")
                                        found_key_folder = True
                                        break

                                # 方法3: 如果前两种方法都不适用，使用父目录+文件名
                                if not found_key_folder:
                                    parent_dir = os.path.basename(os.path.dirname(matching_file))
                                    tex_relative_path = os.path.join(parent_dir, os.path.basename(matching_file))
                                    logger.info(f"使用父目录+文件名相对路径(贴图): {matching_file} -> {tex_relative_path}")

                        # 创建目标贴图文件路径
                        tex_target_file = os.path.join(output_path, tex_relative_path)
                        tex_target_dir = os.path.dirname(tex_target_file)

                        # 确保目标目录存在
                        if not os.path.exists(tex_target_dir):
                            os.makedirs(tex_target_dir, exist_ok=True)

                        # 复制贴图文件
                        shutil.copy2(matching_file, tex_target_file)
                        copied_textures.append({
                            "source": matching_file,
                            "target": tex_target_file,
                            "type": "UDIM",
                            "source_info": texture_source
                        })
                        logger.info(f"复制UDIM贴图: {matching_file} -> {tex_target_file}")
            elif os.path.exists(texture_path):
                # 对于普通贴图，直接复制
                logger.info(f"处理普通贴图: {texture_path}")

                # 提取相对路径 - 保持原始目录结构
                tex_path_parts = texture_path.replace('\\', '/').split('/')

                # 处理不同类型的路径
                if 'filmserver' in tex_path_parts:
                    # 如果路径包含filmserver，以filmserver后的部分作为相对路径
                    tex_server_index = tex_path_parts.index('filmserver')
                    if tex_server_index + 1 < len(tex_path_parts):
                        tex_relative_path = '/'.join(tex_path_parts[tex_server_index+1:])
                    else:
                        tex_relative_path = os.path.basename(texture_path)
                    logger.info(f"从filmserver路径提取普通贴图路径: {texture_path} -> {tex_relative_path}")
                else:
                    # 尝试多种方法来确定合适的相对路径
                    source_dir = os.path.dirname(source_file).replace('\\', '/')
                    tex_dir = os.path.dirname(texture_path).replace('\\', '/')

                    # 方法1: 如果贴图文件在源文件的子目录中，保持相对结构
                    if tex_dir.startswith(source_dir):
                        tex_relative_path = texture_path.replace(source_dir, '').lstrip('/')
                        logger.info(f"使用源文件子目录相对路径(普通贴图): {texture_path} -> {tex_relative_path}")
                    else:
                        # 方法2: 查找关键目录标识符
                        key_folders = ['texture', 'textures', 'tex', 'maps', 'images', 'txt', 'publish', 'USD', 'usd', 'assets']
                        found_key_folder = False

                        tex_dir_parts = tex_dir.split('/')
                        for key_folder in key_folders:
                            if key_folder in tex_dir_parts:
                                # 从关键文件夹开始保留路径结构
                                key_index = tex_dir_parts.index(key_folder)
                                tex_relative_path = '/'.join(tex_dir_parts[key_index:] + [os.path.basename(texture_path)])
                                logger.info(f"使用关键目录标识符相对路径(普通贴图): {texture_path} -> {tex_relative_path}")
                                found_key_folder = True
                                break

                        # 方法3: 如果前两种方法都不适用，使用父目录+文件名
                        if not found_key_folder:
                            parent_dir = os.path.basename(os.path.dirname(texture_path))
                            tex_relative_path = os.path.join(parent_dir, os.path.basename(texture_path))
                            logger.info(f"使用父目录+文件名相对路径(普通贴图): {texture_path} -> {tex_relative_path}")

                # 创建目标贴图文件路径
                tex_target_file = os.path.join(output_path, tex_relative_path)
                tex_target_dir = os.path.dirname(tex_target_file)

                # 确保目标目录存在
                if not os.path.exists(tex_target_dir):
                    os.makedirs(tex_target_dir, exist_ok=True)

                # 复制贴图文件
                shutil.copy2(texture_path, tex_target_file)
                copied_textures.append({
                    "source": texture_path,
                    "target": tex_target_file,
                    "type": texture_type or "texture",
                    "source_info": texture_source
                })
                logger.info(f"复制贴图文件: {texture_path} -> {tex_target_file}")
            else:
                logger.warning(f"贴图文件不存在: {texture_path}，跳过")

        # 返回打包结果
        return {
            "success": True,
            "message": f"打包完成！复制了1个主USD文件，{len(copied_references)}个引用文件和{len(copied_textures)}个贴图文件到 {output_path}",
            "copied_files": {
                "main": target_file,
                "references": copied_references,
                "textures": copied_textures
            }
        }
    except Exception as e:
        logger.error(f"打包文件失败: {str(e)}")
        logger.error(traceback.format_exc())
        return {"success": False, "message": f"打包文件失败: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    import os
    import socket
    import signal
    import sys
    import subprocess
    import time

    # 定义要尝试的端口列表
    ports_to_try = [63080, 63081, 3001]

    # Get port from environment variable, use default 63080 if not set
    env_port = os.environ.get("PORT")
    if env_port:
        try:
            port = int(env_port)
            # If port is specified in environment variable, put it at the front of the list
            if port not in ports_to_try:
                ports_to_try.insert(0, port)
        except ValueError:
            logger.warning(f"Invalid PORT environment variable value: {env_port}, will use default port")

    # 在Windows上尝试终止占用端口的进程
    def kill_process_on_port(port):
        if os.name == 'nt':  # Windows
            try:
                # 使用netstat查找占用端口的进程PID
                cmd = f'netstat -ano | findstr :{port}'
                output = subprocess.check_output(cmd, shell=True).decode('utf-8')

                if output:
                    # 提取PID
                    for line in output.split('\n'):
                        if f':{port}' in line:
                            parts = line.strip().split()
                            if len(parts) >= 5:
                                pid = parts[4]
                                # Terminate process
                                logger.info(f"Attempting to terminate process using port {port} (PID: {pid})")
                                subprocess.call(f'taskkill /F /PID {pid}', shell=True)
                                time.sleep(1)  # Wait for process to terminate
                                return True
            except Exception as e:
                logger.error(f"Error terminating process using port {port}: {str(e)}")
        return False

    # 检查端口是否可用
    def is_port_available(port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False
        finally:
            sock.close()

    # Try to start server on different ports
    for port in ports_to_try:
        if not is_port_available(port):
            logger.warning(f"Port {port} is already in use, trying to release...")
            if kill_process_on_port(port):
                logger.info(f"Successfully released port {port}")
                time.sleep(1)  # Wait for port to be released
            else:
                logger.warning(f"Unable to release port {port}, trying next port")
                continue

        try:
            logger.info(f"Attempting to start server on port {port}")
            uvicorn.run(app, host="127.0.0.1", port=port)
            break  # If successfully started, break the loop
        except OSError as e:
            logger.error(f"Failed to start server on port {port}: {str(e)}")
            continue  # Try next port
    else:
        # If all ports failed
        logger.error(f"All ports {ports_to_try} are unavailable, server startup failed")
        sys.exit(1)
