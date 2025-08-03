# album/admin.py

from django.contrib import admin
from .models import UploadedFile,Folder # 从当前目录的 models.py 中导入 UploadedFile 模型

# 将 UploadedFile 模型注册到 admin 后台管理网站中
admin.site.register(UploadedFile)

admin.site.register(Folder) # 注册 Folder