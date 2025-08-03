# album/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import UploadedFile, Folder
from .forms import FolderForm
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from .forms import FolderForm, UploadFileForm # 确保 UploadFileForm 已导入
from django.core.files.base import ContentFile # 导入 ContentFile
from pathlib import Path # <-- 确保这一行存在或添加它
from django.http import JsonResponse # 导入 JsonResponse
import json # 导入 json
from django.views.decorators.http import require_POST # 导入 require_POST
from django.http import HttpResponse # 注意不是 JsonResponse
import zipfile


import io
from PIL import Image
import pillow_heif
import os

# from pathlib import Path # 导入pathlib方便处理路径 (清理重复导入)

def build_folder_tree(user):
    """
    一个辅助函数，为指定用户构建一个嵌套的文件夹树状数据结构。
    这是实现“移动到...”模态框中层级显示的关键。
    """
    all_folders = Folder.objects.filter(user=user).order_by('name')
    # 创建一个字典映射，方便快速查找，每个节点都包含一个 children 列表
    folder_map = {folder.id: {'id': folder.id, 'name': folder.name, 'children': []} for folder in all_folders}
    
    # 最终的树结构
    tree = []
    
    # 遍历所有文件夹，将它们放到正确的父文件夹的 children 列表中
    for folder in all_folders:
        node = folder_map[folder.id]
        if folder.parent_id and folder.parent_id in folder_map:
            # 如果有父文件夹，就找到它并把自己加进去
            parent_node = folder_map[folder.parent_id]
            parent_node['children'].append(node)
        else:
            # 如果没有父文件夹，说明是顶级文件夹，直接加入树的根部
            tree.append(node)
            
    return tree


@login_required
def file_list(request, folder_id=None):
    """文件和文件夹列表视图（最终版）"""
    current_folder = None
    if folder_id:
        current_folder = get_object_or_404(Folder, id=folder_id, user=request.user)
        folders = current_folder.subfolders.all().order_by('name')
        files = current_folder.files.all().order_by('-uploaded_at')
    else:
        folders = Folder.objects.filter(user=request.user, parent__isnull=True).order_by('name')
        files = UploadedFile.objects.filter(user=request.user, folder__isnull=True).order_by('-uploaded_at')
    
    folder_form = FolderForm()

    # 面包屑导航逻辑 (不变)
    breadcrumbs = []
    temp_folder = current_folder
    while temp_folder:
        breadcrumbs.insert(0, temp_folder)
        temp_folder = temp_folder.parent

    # 【核心改动】调用新的辅助函数来获取层级化的文件夹树
    folder_tree = build_folder_tree(request.user)

    # 【新增】将文件QuerySet转换为JSON友好的列表
    files_for_json = []
    for f in files:
        if f.file:  # 确保文件存在
            files_for_json.append({
                'id': f.id,
                'url': f.file.url,
            })

    context = {
        'current_folder': current_folder,
        'folders': folders,
        'files': files,
        'folder_form': folder_form,
        'breadcrumbs': breadcrumbs,
        'folder_tree': folder_tree,
        # 【新增】将转换后的列表加入context
        'files_for_json': files_for_json,
    }
    return render(request, 'album/file_list.html', context)


@login_required
def create_folder(request, parent_folder_id=None):
    parent_folder = None
    if parent_folder_id:
        parent_folder = get_object_or_404(Folder, id=parent_folder_id, user=request.user)

    if request.method == 'POST':
        form = FolderForm(request.POST)
        if form.is_valid():
            new_folder = form.save(commit=False)
            new_folder.user = request.user
            new_folder.parent = parent_folder
            new_folder.save()
            # 创建后重定向回所在的文件夹
            if parent_folder:
                return redirect('album:file_list_folder', folder_id=parent_folder.id)
            return redirect('album:file_list_root')
    
    # 如果不是POST请求，理论上不应该直接访问这个URL，但为了健壮性，我们重定向
    return redirect('album:file_list_root')


# 2. 在文件末尾，添加下面的 signup 视图函数
def signup(request):
    """处理用户注册"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            # 表单验证通过，创建新用户并保存到数据库
            user = form.save()
            # (可选但推荐) 注册成功后自动为该用户登录
            login(request, user)
            # 重定向到主页
            return redirect('album:file_list_root')
    else:
        # 如果是 GET 请求，显示一个空的注册表单
        form = UserCreationForm()
        
    return render(request, 'registration/signup.html', {'form': form})


@login_required
def upload_file(request, folder_id=None):
    """处理【多个】文件上传，并关联到特定文件夹（支持HEIC格式自动转换）"""
    current_folder = None
    if folder_id:
        current_folder = get_object_or_404(Folder, id=folder_id, user=request.user)

    # 【修改点1】我们现在只处理 POST 请求
    if request.method == 'POST':
        try:
            files_list = request.FILES.getlist('files')
            
            if not files_list:
                return JsonResponse({'success': False, 'error': '没有选择任何文件。'}, status=400)

            for original_file in files_list:
                file_to_save = original_file
                
                if original_file.name.lower().endswith(('.heic', '.heif')):
                    try:
                        pillow_heif.register_heif_opener()
                        heif_image = pillow_heif.read_heif(original_file, convert_hdr_to_8bit=True)
                        image = Image.frombytes(
                            heif_image.mode, heif_image.size, heif_image.data, "raw",
                        )
                        buffer = io.BytesIO()
                        image.save(buffer, format='JPEG', quality=85)
                        new_filename = os.path.splitext(original_file.name)[0] + '.jpg'
                        file_to_save = ContentFile(buffer.getvalue(), name=new_filename)
                    except Exception as e:
                        print(f"转换 HEIC 文件 '{original_file.name}' 失败: {e}")
                        continue

                UploadedFile.objects.create(
                    user=request.user,
                    folder=current_folder,
                    file=file_to_save
                )
            
            # 【修改点2】上传成功后，返回 JSON 响应，而不是 redirect
            return JsonResponse({'success': True})
        
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    # 【修改点3】对于非 POST 请求，也返回 JSON 错误信息
    return JsonResponse({'success': False, 'error': '只接受 POST 请求'}, status=405)

@login_required
def upload_folder(request, folder_id=None):
    """
    处理由 JS fetch 发送的文件夹上传请求（优化版）。
    引入了缓存机制，以提高处理多文件时的效率和健-壮性。
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': '只接受 POST 请求'}, status=405)

    try:
        files_list = request.FILES.getlist('files')
        relative_paths_str = request.POST.get('relative_paths')

        if not files_list or not relative_paths_str:
            return JsonResponse({'success': False, 'error': '缺少文件或路径数据'}, status=400)

        relative_paths = json.loads(relative_paths_str)

        if len(files_list) != len(relative_paths):
            return JsonResponse({'success': False, 'error': '文件和路径数据不匹配'}, status=400)
        
        # 确定上传的基础文件夹
        base_folder = None
        if folder_id:
            base_folder = get_object_or_404(Folder, id=folder_id, user=request.user)

        # 【核心优化】创建一个缓存来存储本次请求中已经找到或创建的文件夹
        # 键是文件夹的完整路径（元组形式），值是文件夹对象
        folder_cache = {}

        # 遍历文件和路径
        for uploaded_file, path_str in zip(files_list, relative_paths):
            path = Path(path_str)
            folder_path_parts = path.parts[:-1]  # 获取除去文件名的所有父目录部分
            file_name = path.name

            # 从基础文件夹开始
            current_parent = base_folder
            
            # 逐级处理路径中的每个部分
            for i, part_name in enumerate(folder_path_parts):
                # 创建一个唯一的、可作为字典键的路径元组
                current_path_tuple = tuple(folder_path_parts[:i+1])

                if current_path_tuple in folder_cache:
                    # 如果缓存中已有，直接使用
                    current_parent = folder_cache[current_path_tuple]
                else:
                    # 如果缓存中没有，则查询或创建，然后存入缓存
                    folder, created = Folder.objects.get_or_create(
                        user=request.user,
                        name=part_name,
                        parent=current_parent
                    )
                    current_parent = folder
                    folder_cache[current_path_tuple] = folder
            
            # 此时，current_parent 就是文件应该在的最终文件夹
            UploadedFile.objects.create(
                user=request.user,
                folder=current_parent,
                file=uploaded_file
                # 你可能还想保存原始文件名，如果你的模型有这个字段的话
                # file_name_original=file_name
            )
        
        return JsonResponse({'success': True, 'message': '文件夹上传成功！'})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': '路径数据JSON格式错误'}, status=400)
    except Exception as e:
        # 捕获所有其他异常
        return JsonResponse({'success': False, 'error': f'服务器内部错误: {str(e)}'}, status=500)


@require_POST # 确保这个视图只接受 POST 请求
@login_required
def delete_file(request, file_id):
    """删除一个文件"""
    # 1. 获取文件对象，同时验证文件存在且属于当前用户
    file_to_delete = get_object_or_404(UploadedFile, id=file_id, user=request.user)

    # 2. 从硬盘上删除物理文件
    if hasattr(file_to_delete, 'file') and file_to_delete.file:
        if os.path.exists(file_to_delete.file.path):
            file_to_delete.file.delete(save=False) # save=False 避免再次保存模型

    # 3. 从数据库中删除记录
    file_to_delete.delete()

    # 5. 重定向回之前的页面
    return redirect(request.META.get('HTTP_REFERER', 'album:file_list_root'))


@require_POST
@login_required
def delete_folder(request, folder_id):
    """删除一个文件夹以及其下的所有内容"""
    folder_to_delete = get_object_or_404(Folder, id=folder_id, user=request.user)

    # 递归删除物理文件
    def delete_files_in_folder(folder):
        # 先删除当前文件夹下的所有物理文件
        for file in folder.files.all():
            if hasattr(file, 'file') and file.file and os.path.exists(file.file.path):
                file.file.delete(save=False)
        
        # 递归删除所有子文件夹下的物理文件
        for subfolder in folder.subfolders.all():
            delete_files_in_folder(subfolder)

    delete_files_in_folder(folder_to_delete)
    
    # 现在可以安全地删除数据库记录了，Django 的 CASCADE 会处理所有子记录
    folder_to_delete.delete()

    return redirect(request.META.get('HTTP_REFERER', 'album:file_list_root'))


@require_POST
@login_required
def batch_delete(request):
    """处理批量删除文件和文件夹的请求"""
    try:
        # 1. 从前端POST请求的body中加载JSON数据
        data = json.loads(request.body)
        file_ids = data.get('files', [])
        folder_ids = data.get('folders', [])

        # 2. 批量处理要删除的文件夹
        if folder_ids:
            folders_to_delete = Folder.objects.filter(id__in=folder_ids, user=request.user)

            # 递归删除物理文件 (和单体删除一样，这是防止孤儿文件的关键)
            def delete_files_in_folder(folder):
                for file in folder.files.all():
                    if hasattr(file, 'file') and file.file and os.path.exists(file.file.path):
                        file.file.delete(save=False)
                for subfolder in folder.subfolders.all():
                    delete_files_in_folder(subfolder)

            for folder in folders_to_delete:
                delete_files_in_folder(folder)

            # 高效地一次性删除所有文件夹的数据库记录
            folders_to_delete.delete()

        # 3. 批量处理要删除的文件
        if file_ids:
            files_to_delete = UploadedFile.objects.filter(id__in=file_ids, user=request.user)

            # 先循环删除所有物理文件
            for file in files_to_delete:
                if hasattr(file, 'file') and file.file and os.path.exists(file.file.path):
                    file.file.delete(save=False)

            # 再高效地一次性删除所有文件的数据库记录
            files_to_delete.delete()

        return JsonResponse({'success': True})

    except Exception as e:
        # 捕获任何可能的异常，并以JSON格式返回错误信息
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    

@require_POST
@login_required
def batch_move(request):
    """处理批量移动文件和文件夹的请求"""
    try:
        data = json.loads(request.body)
        file_ids = data.get('files', [])
        folder_ids = data.get('folders', [])
        destination_folder_id = data.get('destination')

        # 确定目标文件夹
        destination_folder = None
        if destination_folder_id is not None:
            destination_folder = get_object_or_404(Folder, id=destination_folder_id, user=request.user)

        # --- 核心验证：防止将文件夹移动到自身或其子文件夹中 ---
        if destination_folder:
            for folder_id in folder_ids:
                folder_to_move = get_object_or_404(Folder, id=folder_id, user=request.user)
                temp_parent = destination_folder
                while temp_parent is not None:
                    if temp_parent == folder_to_move:
                        return JsonResponse({'success': False, 'error': '不能将文件夹移动到其自己的子文件夹中。'}, status=400)
                    temp_parent = temp_parent.parent

        # 更新文件的归属文件夹
        if file_ids:
            UploadedFile.objects.filter(id__in=file_ids, user=request.user).update(folder=destination_folder)

        # 更新文件夹的父文件夹
        if folder_ids:
            Folder.objects.filter(id__in=folder_ids, user=request.user).update(parent=destination_folder)

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    

@login_required
def download_folder_as_zip(request, folder_id):
    """将一个文件夹及其所有内容打包成 ZIP 文件并提供下载"""
    folder = get_object_or_404(Folder, id=folder_id, user=request.user)

    # 在内存中创建一个 BytesIO 对象，用于存储 ZIP 数据
    zip_buffer = io.BytesIO()

    # 创建一个 ZipFile 对象，把它关联到我们的内存缓冲区
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:

        # 这是一个递归的辅助函数，用于将文件夹内容添加到 ZIP 文件中
        def add_folder_to_zip(current_folder, base_path=""):
            # 【关键修改】首先为当前文件夹本身创建一个目录条目
            # 这确保了即使文件夹是空的，它也会出现在ZIP文件中
            if base_path:
                zf.writestr(base_path + '/', '')

            # 将当前文件夹下的文件添加到 ZIP 中
            for file in current_folder.files.all():
                if hasattr(file, 'file') and file.file and os.path.exists(file.file.path):
                    file_path = file.file.path
                    arc_name = os.path.join(base_path, os.path.basename(file.file.name))
                    zf.write(file_path, arcname=arc_name)

            # 递归处理所有子文件夹
            for subfolder in current_folder.subfolders.all():
                # 创建新的相对路径，并递归调用
                new_base_path = os.path.join(base_path, subfolder.name)
                add_folder_to_zip(subfolder, new_base_path)

        # 从请求的文件夹开始递归
        add_folder_to_zip(folder, base_path=folder.name)

    # 准备 HTTP 响应
    zip_buffer.seek(0) # 将缓冲区的指针移到开头
    response = HttpResponse(zip_buffer.read(), content_type='application/zip')
    # 设置 Content-Disposition 头，让浏览器弹出下载对话框
    response['Content-Disposition'] = f'attachment; filename="{folder.name}.zip"'

    return response
    

# =================================================================
# 【新增功能】下面是新添加的 batch_download 视图
# =================================================================

@require_POST
@login_required
def batch_download(request):
    """处理批量下载文件和文件夹的请求"""
    file_ids = request.POST.getlist('file_ids')
    folder_ids = request.POST.getlist('folder_ids')

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        
        # 为了不与 download_folder_as_zip 的内部函数冲突，我们在这里定义一个独立的辅助函数
        # 这是为了严格遵守“不重构”原则
        def add_folder_to_zip_for_batch(folder, base_path=""):
            # 【关键修改】首先为当前文件夹本身创建一个目录条目
            if base_path:
                zf.writestr(base_path + '/', '')

            for file in folder.files.all():
                if hasattr(file, 'file') and file.file and os.path.exists(file.file.path):
                    file_path = file.file.path
                    arc_name = os.path.join(base_path, os.path.basename(file.file.name))
                    zf.write(file_path, arcname=arc_name)
            for subfolder in folder.subfolders.all():
                new_base_path = os.path.join(base_path, subfolder.name)
                add_folder_to_zip_for_batch(subfolder, new_base_path)

        # 1. 处理选中的文件夹
        if folder_ids:
            folders_to_download = Folder.objects.filter(id__in=folder_ids, user=request.user)
            for folder in folders_to_download:
                add_folder_to_zip_for_batch(folder, base_path=folder.name)
        
        # 2. 处理选中的顶层文件
        if file_ids:
            files_to_download = UploadedFile.objects.filter(id__in=file_ids, user=request.user)
            for file in files_to_download:
                if hasattr(file, 'file') and file.file and os.path.exists(file.file.path):
                    zf.write(file.file.path, arcname=os.path.basename(file.file.name))

    # 3. 创建并返回ZIP文件响应
    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="download.zip"' 
    return response


@require_POST
@login_required
def rename_item(request):
    """处理文件或文件夹的重命名请求"""
    try:
        data = json.loads(request.body)
        item_type = data.get('item_type')
        item_id = data.get('item_id')
        new_name = data.get('new_name', '').strip()

        if not new_name:
            return JsonResponse({'success': False, 'error': '名称不能为空。'}, status=400)

        if item_type == 'folder':
            folder = get_object_or_404(Folder, id=item_id, user=request.user)
            folder.name = new_name
            folder.save()
            return JsonResponse({'success': True, 'new_name': folder.name})
        
        elif item_type == 'file':
            file_obj = get_object_or_404(UploadedFile, id=item_id, user=request.user)
            
            # --- 重命名物理文件 ---
            old_path = file_obj.file.path
            # 分离文件名和扩展名
            filename, file_extension = os.path.splitext(os.path.basename(old_path))
            # 创建新的文件名（保留原始扩展名）
            new_filename = new_name + file_extension
            
            # 如果新旧名字相同，则什么都不做
            if new_filename == os.path.basename(old_path):
                 return JsonResponse({'success': True, 'new_name': new_name})

            # 获取文件所在的目录
            directory = os.path.dirname(old_path)
            new_path = os.path.join(directory, new_filename)
            
            # 检查新文件名是否已存在
            if os.path.exists(new_path):
                return JsonResponse({'success': False, 'error': '该位置已存在同名文件。'}, status=400)

            # 执行重命名
            os.rename(old_path, new_path)
            
            # --- 更新数据库中的文件路径 ---
            # file.name 是相对于 MEDIA_ROOT 的路径
            new_db_path = os.path.join(os.path.dirname(file_obj.file.name), new_filename)
            file_obj.file.name = new_db_path
            file_obj.save()
            
            return JsonResponse({'success': True, 'new_name': os.path.basename(new_db_path)})
        
        else:
            return JsonResponse({'success': False, 'error': '无效的项目类型。'}, status=400)

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    

# album/views.py
@login_required
def search(request):
    """处理文件和文件夹的搜索请求"""
    # 1. 从 GET 请求中获取 'q' 参数作为查询词
    query = request.GET.get('q', '').strip()

    # 2. 如果查询词不为空，则执行搜索
    if query:
        # 使用 __icontains 进行不区分大小写的模糊查询
        # 同时确保只搜索属于当前用户的内容
        found_folders = Folder.objects.filter(
            user=request.user,
            name__icontains=query
        ).order_by('name')
        
        # 对于文件，我们在文件名（file字段）中搜索
        found_files = UploadedFile.objects.filter(
            user=request.user,
            file__icontains=query
        ).order_by('-uploaded_at')
    else:
        # 如果没有查询词，则返回空列表
        found_folders = Folder.objects.none()
        found_files = UploadedFile.objects.none()

    # 搜索结果页面也需要文件夹树来进行“移动”操作
    folder_tree = build_folder_tree(request.user)

    context = {
        'query': query,
        'folders': found_folders,
        'files': found_files,
        'folder_tree': folder_tree,
    }
    
    return render(request, 'album/search_results.html', context)