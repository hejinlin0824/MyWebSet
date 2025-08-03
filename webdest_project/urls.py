# webdest_project/urls.py

from django.contrib import admin
from django.urls import path, include  # 需要导入 include
from django.conf import settings  # 导入项目配置
from django.conf.urls.static import static  # 导入处理静态文件的辅助函数
from album import views

urlpatterns = [
    path('admin/', admin.site.urls),
    # 将所有来自网站根目录的请求，都转交给 album 应用的 urls.py 去处理
    path('', include('album.urls')), 
    # 关键！添加这一行来包含所有认证相关的URL。
    # 'login', 'logout', 'password_reset' 等URL的名字都由它提供。
    path('accounts/', include('django.contrib.auth.urls')),
    # 将我们自己的 signup URL 放在这里，并为其分配一个全局的名字
    path('accounts/signup/', views.signup, name='signup'),
]

# 这是一个非常重要的配置，它只在开发模式(DEBUG=True)下生效
# 它告诉Django，当浏览器请求 /media/ 开头的URL时，
# 去 MEDIA_ROOT 指定的文件夹里寻找并提供文件。
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)