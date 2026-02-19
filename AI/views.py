import json
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.conf import settings
from .models import ChatSession, ChatMessage

# ================= AUTH VIEWS =================
def login_view(request):
    if request.user.is_authenticated: return redirect('chat')
    if request.method == 'POST':
        u, p = request.POST.get('username', '').strip(), request.POST.get('password', '')
        user = authenticate(username=u, password=p)
        if user: login(request, user); return redirect('chat')
        else: messages.error(request, 'Xato!')
    return render(request, 'login.html')

def register_view(request):
    if request.user.is_authenticated: return redirect('chat')
    if request.method == 'POST':
        u, p1 = request.POST.get('username', '').strip(), request.POST.get('password1', '')
        if User.objects.filter(username=u).exists(): messages.error(request, 'Band!')
        else: User.objects.create_user(username=u, password=p1); return redirect('login')
    return render(request, 'register.html')

def logout_view(request):
    logout(request); return redirect('login')

# ================= CHAT VIEWS =================
@login_required(login_url='login')
def chat_view(request):
    sessions = ChatSession.objects.filter(user=request.user).order_by('-id')
    session_id = request.GET.get('session')
    current_session = get_object_or_404(ChatSession, id=session_id, user=request.user) if session_id else None
    return render(request, 'chat.html', {
        'sessions': sessions,
        'current_session': current_session,
        'chat_messages': current_session.messages.all().order_by('id') if current_session else []
    })

@login_required(login_url='login')
def new_session(request):
    s = ChatSession.objects.create(user=request.user, title="Yangi suhbat")
    return redirect(f'/chat/?session={s.id}')

@login_required(login_url='login')
def delete_session(request, session_id):
    get_object_or_404(ChatSession, id=session_id, user=request.user).delete()
    return redirect('chat')

# ================= OPENROUTER CORE =================
@login_required(login_url='login')
def send_message(request):
    if request.method != 'POST': return JsonResponse({'error': '405'})
    
    try:
        data = json.loads(request.body)
        user_msg = data.get('message', '').strip()
        s_id = data.get('session_id')
        
        session = get_object_or_404(ChatSession, id=s_id, user=request.user)
        ChatMessage.objects.create(session=session, role='user', content=user_msg)

        # OpenRouter-da hozir ishlayotgan bepul modellar ro'yxati
        models_to_try = [
            "google/gemini-2.0-flash-lite-preview-02-05:free",
            "meta-llama/llama-3.1-8b-instruct:free",
            "mistralai/mistral-7b-instruct:free",
            "openrouter/auto" # Oxirgi chora
        ]
        
        ai_reply = ""
        debug_info = ""

        for model in models_to_try:
            try:
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://127.0.0.1:8000/", # Screenshotdagi manzilingiz
                    },
                    data=json.dumps({
                        "model": model,
                        "messages": [{"role": "user", "content": user_msg}]
                    }),
                    timeout=15
                )

                if response.status_code == 200:
                    ai_reply = response.json()['choices'][0]['message']['content']
                    break
                else:
                    debug_info += f"{model}: {response.status_code} | "
            except:
                continue

        if not ai_reply:
            ai_reply = f"Modellar javob bermadi. OpenRouter logi: {debug_info}"

        ChatMessage.objects.create(session=session, role='assistant', content=ai_reply)
        return JsonResponse({'reply': ai_reply, 'session_id': session.id})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)