

from django.contrib import admin
from django.urls import path
from AI import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('',          views.chat_view,    name='chat'),
    path('chat/',     views.chat_view,    name='chat'),
    path('login/',    views.login_view,   name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/',   views.logout_view,  name='logout'),

    # Chat API
    path('chat/new/',              views.new_session,  name='new_session'),
    path('chat/delete/<int:session_id>/', views.delete_session, name='delete_session'),
    path('chat/send/',             views.send_message, name='send_message'),
]