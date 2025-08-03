# album/urls.py
from django.urls import path
from . import views

app_name = 'album'

urlpatterns = [
    # 根目录
    path('', views.file_list, name='file_list_root'),

    # 查看特定文件夹内容
    path('folder/<int:folder_id>/', views.file_list, name='file_list_folder'),
    # 创建文件夹
    path('folder/create/', views.create_folder, name='create_folder'),
    # (高级) 在特定文件夹内创建子文件夹
    path('folder/<int:parent_folder_id>/create/', views.create_folder, name='create_subfolder'),

    # 新增！文件上传的URL
    path('upload/', views.upload_file, name='upload_file_root'),
    path('folder/<int:folder_id>/upload/', views.upload_file, name='upload_file_folder'),

    # 新增！文件夹上传的 URL
    path('folder/upload/', views.upload_folder, name='upload_folder_root'),
    path('folder/<int:folder_id>/upload-folder/', views.upload_folder, name='upload_folder_subfolder'),

    # 新增！删除文件的 URL
    path('file/<int:file_id>/delete/', views.delete_file, name='delete_file'),

     # 新增！删除文件夹的 URL
    path('folder/<int:folder_id>/delete/', views.delete_folder, name='delete_folder'),

    # 新增！批量删除的 URL
    path('batch-delete/', views.batch_delete, name='batch_delete'),

    # 新增！批量移动的 URL
    path('batch-move/', views.batch_move, name='batch_move'),

    # 新增！文件夹打包下载的 URL
    path('folder/<int:folder_id>/download/', views.download_folder_as_zip, name='download_folder_as_zip'),

     # 新增！批量打包下载的 URL
    path('batch-download/', views.batch_download, name='batch_download'),
    # 新增！重命名功能的 URL
    path('rename-item/', views.rename_item, name='rename_item'),

    # 新增！搜索功能的 URL
    path('search/', views.search, name='search'),
]